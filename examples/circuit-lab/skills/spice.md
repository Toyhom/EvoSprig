# Small circuit design

For an RC low-pass, `fc = 1/(2*pi*R*C)`. A roughly 1 kHz example is:

    RC low pass
    V1 in 0 DC 0 AC 1
    R1 in out 1k
    C1 out 0 159n
    .end

AC runs from 10 Hz to 100 kHz. `gain` is the linear low-frequency gain; `cutoff_hz` is the relative -3 dB crossing.

For a half-wave rectifier, use `V1 in 0 SIN(0 5 100)`, a diode from in to out, a grounded load, and a smoothing capacitor. Supply a `.model D1 D(...)` and use its model name on the diode. Transient runs to 100 ms; mean voltage and ripple are measured over the last quarter. A larger capacitor reduces ripple but increases charging current.

For a simple ideal closed-loop amplifier, use a voltage-controlled voltage source with a finite high gain and a resistor feedback divider. Example: `Eamp out 0 in feedback 100k`, `R1 out feedback 10k`, `R2 feedback 0 10k`. This gives a closed-loop gain near 2. Label the ideal amplifier assumption in the explanation.

Provide only title, components, `.model`, `.param`, `.options`, `.end`. Do not use control blocks, file includes or external libraries. Keep quoted expressions out; use numeric component values. All electrical connections require ground reference.

A complete ideal non-inverting gain-2 circuit is:

    Non-inverting amplifier
    Vin in 0 DC 0 AC 1
    Eop out 0 in fb 100000
    Rf out fb 10000
    Rg fb 0 10000
    Rload out 0 1000000
    .end

The Eop line has six fields. It represents V(out)-V(0)=100000*(V(in)-V(fb)). The signal is on the positive control input and the divider is on the negative control input. Do not omit `0 in`, swap the control nodes or connect both control inputs to the feedback network. A zero output makes dB undefined; inspect the input signal path before altering resistor values.
