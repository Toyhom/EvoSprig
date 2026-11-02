# Software team — baseline

## Html

```json
"<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n  <meta charset=\"UTF-8\">\n  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">\n  <title>Meeting Timer · calm white</title>\n  <style>\n    * {\n      box-sizing: border-box;\n      margin: 0;\n      padding: 0;\n    }\n\n    body {\n      background: #fcfcfc;\n      font-family: system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', sans-serif;\n      display: flex;\n      align-items: center;\n      justify-content: center;\n      min-height: 100vh;\n      margin: 0;\n      padding: 1.5rem;\n      color: #1e1e1e;\n      line-height: 1.5;\n    }\n\n    .timer-card {\n      background: #ffffff;\n      max-width: 36rem;\n      width: 100%;\n      padding: 2.5rem 2rem 2.25rem;\n      border-radius: 2rem;\n      box-shadow: 0 8px 24px rgba(0, 0, 0, 0.02), 0 2px 6px rgba(0, 0, 0, 0.02);\n      border: 1px solid #f0f0f0;\n      transition: box-shadow 0.1s ease;\n    }\n\n    h1 {\n      font-size: 1.6rem;\n      font-weight: 450;\n      letter-spacing: -0.01em;\n      color: #2c2c2c;\n      margin-bottom: 1.75rem;\n      border-bottom: 1px solid #f0f0f0;\n      padding-bottom: 0.9rem;\n    }\n\n    .input-group {\n      display: flex;\n      flex-wrap: wrap;\n      align-items: center;\n      gap: 0.75rem 1rem;\n      margin-bottom: 1.5rem;\n    }\n\n    .input-group label {\n      font-size: 1rem;\n      font-weight: 400;\n      color: #3a3a3a;\n      letter-spacing: 0.01em;\n    }\n\n    .input-group input {\n      width: 7.5rem;\n      padding: 0.7rem 1rem;\n      font-size: 1.1rem;\n      font-family: inherit;\n      border: 1px solid #e2e2e2;\n      border-radius: 1.5rem;\n      background: #ffffff;\n      color: #1e1e1e;\n      outline: none;\n      transition: border-color 0.1s, box-shadow 0.1s;\n      text-align: center;\n      font-variant-numeric: tabular-nums;\n    }\n\n    .input-group input:focus-visible {\n      border-color: #b0b0b0;\n      box-shadow: 0 0 0 3px rgba(0, 0, 0, 0.04);\n    }\n\n    .input-group input::placeholder {\n      color: #b0b0b0;\n      font-weight: 300;\n    }\n\n    .error-message {\n      font-size: 0.9rem;\n      color: #b34a4a;\n      background: #fef8f8;\n      padding: 0.5rem 1rem;\n      border-radius: 2rem;\n      margin-top: 0.25rem;\n      margin-bottom: 0.5rem;\n      display: inline-block;\n      border-left: 3px solid #d9b0b0;\n      width: auto;\n      min-height: 2.2rem;\n      line-height: 1.4;\n      transition: opacity 0.1s;\n    }\n\n    .error-message.hidden {\n      display: none;\n    }\n\n    .timer-display {\n      background: #fafafa;\n      border-radius: 2rem;\n      padding: 1.75rem 1rem;\n      margin: 1.5rem 0 1.75rem;\n      text-align: center;\n      border: 1px solid #f0f0f0;\n    }\n\n    .time {\n      font-size: 4.5rem;\n      font-weight: 350;\n      letter-spacing: 0.02em;\n      font-variant-numeric: tabular-nums;\n      color: #1e1e1e;\n      line-height: 1.2;\n      margin-bottom: 0.25rem;\n    }\n\n    .state {\n      font-weight: 400;\n      color: #5e5e5e;\n      letter-spacing: 0.08em;\n      background: #ffffff;\n      display: inline-block;\n      padding: 0.3rem 1.2rem;\n      border-radius: 3rem;\n      border: 1px solid #ececec;\n      font-size: 0.9rem;\n    }\n\n    .controls {\n      display: flex;\n      flex-wrap: wrap;\n      gap: 0.75rem;\n      justify-content: center;\n      margin-top: 0.5rem;\n    }\n\n    button {\n      font-family: inherit;\n      font-size: 1rem;\n      font-weight: 450;\n      padding: 0.8rem 1.8rem;\n      border-radius: 3rem;\n      border: 1px solid #e0e0e0;\n      background: #ffffff;\n      color: #1e1e1e;\n      cursor: pointer;\n      transition: background 0.1s, border-color 0.1s, box-shadow 0.1s;\n      min-width: 6.5rem;\n      letter-spacing: 0.01em;\n      box-shadow: 0 1px 2px rgba(0, 0, 0, 0.01);\n    }\n\n    button:hover {\n      background: #f7f7f7;\n      border-color: #d0d0d0;\n    }\n\n    button:active {\n      background: #f0f0f0;\n    }\n\n    button:focus-visible {\n      outline: 2px solid #b0b0b0;\n      outline-offset: 2px;\n      border-color: #b0b0b0;\n      box-shadow: 0 0 0 4px rgba(0, 0, 0, 0.02);\n    }\n\n    #startBtn {\n      background: #f5f5f5;\n      border-color: #e0e0e0;\n      font-weight: 500;\n    }\n\n    #startBtn:hover {\n      background: #efefef;\n    }\n\n    button:disabled {\n      opacity: 0.5;\n      cursor: not-allowed;\n      background: #fafafa;\n      border-color: #ececec;\n    }\n\n    .keyboard-note {\n      margin-top: 1.75rem;\n      font-size: 0.8rem;\n      color: #9a9a9a;\n      text-align: center;\n      border-top: 1px solid #f3f3f3;\n      padding-top: 1.25rem;\n      letter-spacing: 0.01em;\n    }\n\n    @media (max-width: 480px) {\n      .timer-card {\n        padding: 1.75rem 1.25rem;\n      }\n      .time {\n        font-size: 3.5rem;\n      }\n      button {\n        padding: 0.7rem 1.2rem;\n        min-width: 5rem;\n        font-size: 0.95rem;\n      }\n      .input-group input {\n        width: 6rem;\n      }\n    }\n  </style>\n</head>\n<body>\n  <main class=\"timer-card\">\n    <h1>Meeting timer</h1>\n\n    <div class=\"input-group\">\n      <label for=\"minutesInput\">Minutes</label>\n      <input\n        type=\"text\"\n        id=\"minutesInput\"\n        inputmode=\"numeric\"\n        placeholder=\"e.g. 5\"\n        value=\"5\"\n        aria-describedby=\"durationError\"\n        autocomplete=\"off\"\n      />\n    </div>\n    <div id=\"durationError\" class=\"error-message hidden\" role=\"alert\" aria-live=\"polite\"></div>\n\n    <div class=\"timer-display\">\n      <div class=\"time\" id=\"timeDisplay\" aria-live=\"polite\" aria-atomic=\"true\">05:00</div>\n      <div class=\"state\" id=\"stateDisplay\">Idle</div>\n    </div>\n\n    <div class=\"controls\">\n      <button id=\"startBtn\" type=\"button\">Start</button>\n      <button id=\"pauseBtn\" type=\"button\">Pause</button>\n      <button id=\"resetBtn\" type=\"button\">Reset</button>\n    </div>\n\n    <div class=\"keyboard-note\">\n      Tab to navigate · Enter or Space to activate\n    </div>\n  </main>\n\n  <script>\n    (function() {\n      'use strict';\n\n      const minutesInput = document.getElementById('minutesInput');\n      const timeDisplay = document.getElementById('timeDisplay');\n      const stateDisplay = document.getElementById('stateDisplay');\n      const startBtn = document.getElementById('startBtn');\n      const pauseBtn = document.getElementById('pauseBtn');\n      const resetBtn = document.getElementById('resetBtn');\n      const errorDiv = document.getElementById('durationError');\n\n      let totalSeconds = 300;\n      let remainingSeconds = 300;\n      let timerInterval = null;\n      let currentState = 'Idle';\n\n      function formatTime(seconds) {\n        const mins = Math.floor(seconds / 60);\n        const secs = seconds % 60;\n        return String(mins).padStart(2, '0') + ':' + String(secs).padStart(2, '0');\n      }\n\n      function updateDisplay() {\n        timeDisplay.textContent = formatTime(remainingSeconds);\n        stateDisplay.textContent = currentState;\n      }\n\n      function clearTimerInterval() {\n        if (timerInterval !== null) {\n          clearInterval(timerInterval);\n          timerInterval = null;\n        }\n      }\n\n      function showError(message) {\n        errorDiv.textContent = message;\n        errorDiv.classList.remove('hidden');\n      }\n\n      function hideError() {\n        errorDiv.textContent = '';\n        errorDiv.classList.add('hidden');\n      }\n\n      function parseDurationFromInput() {\n        const raw = minutesInput.value.trim();\n        if (raw === '') {\n          showError('Please enter a duration in minutes.');\n          return null;\n        }\n        const num = Number(raw);\n        if (!isFinite(num) || isNaN(num)) {\n          showError('Please enter a valid number.');\n          return null;\n        }\n        if (num <= 0) {\n          showError('Duration must be greater than zero.');\n          return null;\n        }\n        const seconds = Math.round(num * 60);\n        if (seconds <= 0) {\n          showError('Duration must be at least 1 second.');\n          return null;\n        }\n        return seconds;\n      }\n\n      function startTimer() {\n        if (currentState === 'Running') {\n          return;\n        }\n\n        if (currentState === 'Finished') {\n          remainingSeconds = totalSeconds;\n        }\n\n        if (currentState === 'Idle') {\n          const parsedSeconds = parseDurationFromInput();\n          if (parsedSeconds === null) {\n            return;\n          }\n          totalSeconds = parsedSeconds;\n          remainingSeconds = totalSeconds;\n          hideError();\n        }\n\n        if (remainingSeconds <= 0) {\n          remainingSeconds = totalSeconds;\n        }\n\n        clearTimerInterval();\n\n        currentState = 'Running';\n        updateDisplay();\n\n        timerInterval = setInterval(function() {\n          if (remainingSeconds > 0) {\n            remainingSeconds -= 1;\n          }\n\n          updateDisplay();\n\n          if (remainingSeconds <= 0) {\n            clearTimerInterval();\n            currentState = 'Finished';\n            remainingSeconds = 0;\n            updateDisplay();\n          }\n        }, 1000);\n      }\n\n      function pauseTimer() {\n        if (currentState !== 'Running') {\n          return;\n        }\n        clearTimerInterval();\n        currentState = 'Paused';\n        updateDisplay();\n      }\n\n      function resetTimer() {\n        clearTimerInterval();\n        remainingSeconds = totalSeconds;\n        currentState = 'Idle';\n        updateDisplay();\n        hideError();\n      }\n\n      startBtn.addEventListener('click', startTimer);\n      pauseBtn.addEventListener('click', pauseTimer);\n      resetBtn.addEventListener('click', resetTimer);\n\n      minutesInput.addEventListener('input', function() {\n        hideError();\n      });\n\n      minutesInput.value = '5';\n      totalSeconds = 300;\n      remainingSeconds = 300;\n      currentState = 'Idle';\n      updateDisplay();\n      hideError();\n\n      window.addEventListener('beforeunload', function() {\n        clearTimerInterval();\n      });\n    })();\n  </script>\n</body>\n</html>"
```

## Preview

```json
{
  "artifacts": [
    {
      "bytes": 24510,
      "mime": "image/png",
      "name": "preview.png",
      "url": "release-baseline-2-2.png"
    }
  ],
  "checks": [
    {
      "expected": "Running",
      "observed": "Running",
      "passed": true,
      "selector": "#stateDisplay"
    },
    {
      "expected": "Paused",
      "observed": "Paused",
      "passed": true,
      "selector": "#stateDisplay"
    },
    {
      "expected": "Idle",
      "observed": "Idle",
      "passed": true,
      "selector": "#stateDisplay"
    },
    {
      "expected": "02:00",
      "observed": "02:00",
      "passed": true,
      "selector": "#timeDisplay"
    }
  ],
  "errors": [],
  "text": "Meeting timer\nMinutes\n02:00\nIdle\nStart\nPause\nReset\nTab to navigate · Enter or Space to activate",
  "title": "Meeting Timer · calm white"
}
```

## Summary

# Delivery Note — Meeting Timer

## Implemented Features
- **Duration input** in minutes with validation that rejects nonpositive values.
- **Start / Pause / Reset** controls with a live state display (`Idle`, `Running`, `Paused`).
- **Remaining time display** in `MM:SS` format.
- **Duplicate-interval guard**: repeated Start clicks do not spawn additional timers.
- **Keyboard-friendly controls**: native buttons with visible focus, Tab navigation, Enter/Space activation.
- **Calm white design** in a single self-contained HTML file.

## Browser Check Outcomes
All four automated checks passed:
- `#stateDisplay` → **Running** after Start ✅
- `#stateDisplay` → **Paused** after Pause ✅
- `#stateDisplay` → **Idle** after Reset ✅
- `#timeDisplay` → **02:00** for a 2-minute setting ✅

No console errors were reported.

## Remaining Defects
None observed in the receipt. The screenshot artifact (`preview.png`) was captured but not visually inspected here; no failing checks or errors indicate outstanding issues.
