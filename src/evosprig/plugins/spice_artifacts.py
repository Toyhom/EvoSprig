"""Bounded SPICE execution with fixed analysis commands and readable waveforms."""

import math
import os
import re
import shutil
import subprocess
from html import escape


def simulate(destination, netlist, analysis, target):
    binary = os.environ.get("EVOSPRIG_NGSPICE") or shutil.which("ngspice")
    if not binary:
        raise ValueError("Install ngspice or set EVOSPRIG_NGSPICE to its executable")
    lines = netlist.splitlines()
    if not lines:
        return {"ok": False, "error": "A title and component lines are required"}
    allowed = {".model", ".param", ".options", ".end"}
    for line in lines[1:]:
        stripped = line.strip()
        if not stripped or stripped.startswith("*"):
            continue
        token = stripped.split()[0].lower()
        if (token.startswith(".") and token not in allowed) or not re.match(r"^[rcldviqmefgbhk.+]", token):
            return {"ok": False, "error": "Use component definitions, .model and .param; analysis commands are provided by the tool"}
        counts = {"r": 4, "c": 4, "l": 4, "d": 4, "v": 4, "i": 4, "e": 6, "g": 6, "f": 5, "h": 5, "q": 5, "m": 6, "k": 4}
        if token[0] in counts and len(stripped.split()) < counts[token[0]]:
            detail = " E/G syntax: name out+ out- control+ control- gain (six tokens)." if token[0] in {"e", "g"} else ""
            return {"ok": False, "error": f"Incomplete component line: {stripped}." + detail}
        if any(character in stripped for character in [';', '`', '$', '\\', '"', "'"]):
            return {"ok": False, "error": "Shell, file and quoted commands are not accepted"}
    body = "\n".join(line for line in lines if line.strip().lower() != ".end")
    if analysis == "ac":
        command = "ac dec 60 10 100000\nwrdata waveform.tsv vdb(out) vp(out)"
    else:
        command = "tran 5u 100m\nwrdata waveform.tsv v(out) v(in)"
    body += "\n.control\nset wr_singlescale\nset wr_vecnames\n" + command + "\nquit\n.endc\n.end\n"
    (destination / "circuit.cir").write_text(body)
    environment = {**os.environ, "SPICE_ASCIIRAWFILE": "1"}
    # A deployment may point to an extracted installation without changing system files.
    with (destination / "simulation.log").open("w") as log:
        try:
            completed = subprocess.run([binary, "-n", "-b", "circuit.cir"], cwd=destination,
                                       env=environment, stdout=log, stderr=subprocess.STDOUT, timeout=40)
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": "Simulation exceeded 40 seconds"}
    output = destination / "waveform.tsv"
    if completed.returncode or not output.is_file():
        return {"ok": False, "error": (destination / "simulation.log").read_text()[-5000:]}
    samples = []
    for line in output.read_text().splitlines()[1:]:
        try:
            values = [float(value) for value in line.split()]
        except ValueError:
            continue
        if len(values) >= 3 and all(math.isfinite(value) for value in values):
            samples.append(values[:3])
    if not samples:
        return {"ok": False, "error": "No finite waveform samples returned"}
    if analysis == "ac":
        gain = samples[0][1]
        cutoff = None
        for previous, current in zip(samples, samples[1:]):
            threshold = gain - 3.0103
            if previous[1] >= threshold >= current[1]:
                fraction = (threshold-previous[1])/(current[1]-previous[1])
                cutoff = math.exp(math.log(previous[0])+fraction*math.log(current[0]/previous[0]))
                break
        metrics = {"low_frequency_gain_db": gain, "gain": 10**(gain/20), "cutoff_hz": cutoff}
    else:
        settled = samples[len(samples)*3//4:]
        values = [row[1] for row in settled]
        # Adaptive time steps require integration instead of a sample-count average.
        area = sum((b[0]-a[0])*(a[1]+b[1])/2 for a,b in zip(settled,settled[1:]))
        duration = settled[-1][0]-settled[0][0]
        metrics = {"mean_voltage": area/duration, "ripple_v": max(values)-min(values),
                   "peak_voltage": max(row[1] for row in samples)}
    checks = []
    for key, expectation in target.items():
        value = metrics.get(key)
        valid = isinstance(expectation, dict) and set(expectation) <= {"min", "max"}
        passed = valid and value is not None and expectation.get("min", -math.inf) <= value <= expectation.get("max", math.inf)
        checks.append({"metric": key, "value": value, "expected": expectation, "passed": passed})
    xs = [math.log10(row[0]) if analysis == "ac" else row[0] for row in samples]
    ys = [row[1] for row in samples]
    xmin,xmax,ymin,ymax = min(xs),max(xs),min(ys),max(ys)
    padding = max(.1, (ymax-ymin)*.1)
    ymin,ymax = ymin-padding,ymax+padding
    stride = max(1,len(xs)//1200)
    points = " ".join(f"{70+840*(xs[i]-xmin)/(xmax-xmin):.1f},{400-310*(ys[i]-ymin)/(ymax-ymin):.1f}" for i in range(0,len(xs),stride))
    label = "Frequency (Hz, log scale) / gain (dB)" if analysis == "ac" else "Time (s) / output (V)"
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="960" height="500" viewBox="0 0 960 500"><rect width="960" height="500" fill="white"/><g font-family="sans-serif" fill="#253245"><text x="60" y="40" font-size="24">{escape(lines[0][:70])}</text><path d="M70 80V400H920" fill="none" stroke="#b2bdc9"/><polyline points="{points}" fill="none" stroke="#2864ad" stroke-width="3"/><text x="70" y="450" font-size="18">{label}</text>'
    for fraction in [0,.25,.5,.75,1]:
        x = xmin+(xmax-xmin)*fraction
        value = 10**x if analysis == "ac" else x
        svg += f'<text x="{60+840*fraction}" y="425" font-size="13">{value:.3g}</text>'
    svg += f'<text x="10" y="90" font-size="13">{ymax:.2f}</text><text x="10" y="400" font-size="13">{ymin:.2f}</text></g></svg>'
    (destination / "waveform.svg").write_text(svg)
    return {"ok": True, "accepted": all(check["passed"] for check in checks), "metrics": metrics,
            "checks": checks, "samples": len(samples), "files": ["circuit.cir", "waveform.tsv", "waveform.svg"]}
