/**
 * Client-side countdown timer for LearnTracker.
 * Manages real-time countdown display, start/stop button interactions,
 * and uses localStorage to persist running timer state across page refreshes.
 */
(function () {
  "use strict";

  // Key used in localStorage to track which timers are currently active
  const STORAGE_KEY = "learntracker_active_timers";

  /**
   * Retrieve the map of active timers from localStorage.
   * Returns an object mapping skill IDs to their start ISO timestamps.
   */
  function getActiveTimers() {
    try {
      return JSON.parse(localStorage.getItem(STORAGE_KEY)) || {};
    } catch {
      return {};
    }
  }

  /**
   * Save a timer's start timestamp to localStorage for persistence across refreshes.
   */
  function setActiveTimer(skillId, startIso) {
    const timers = getActiveTimers();
    timers[skillId] = startIso;
    localStorage.setItem(STORAGE_KEY, JSON.stringify(timers));
  }

  /**
   * Remove a timer from localStorage when it has been stopped.
   */
  function clearActiveTimer(skillId) {
    const timers = getActiveTimers();
    delete timers[skillId];
    localStorage.setItem(STORAGE_KEY, JSON.stringify(timers));
  }

  /**
   * Format seconds into a HH:MM:SS countdown string.
   * Clamps negative values to zero.
   */
  function formatCountdown(totalSeconds) {
    if (totalSeconds < 0) totalSeconds = 0;
    const h = Math.floor(totalSeconds / 3600);
    const m = Math.floor((totalSeconds % 3600) / 60);
    const s = totalSeconds % 60;
    return (
      String(h).padStart(2, "0") +
      ":" +
      String(m).padStart(2, "0") +
      ":" +
      String(s).padStart(2, "0")
    );
  }

  /**
   * Initialize all skill cards on the page — set up timers and button handlers.
   */
  function initCards() {
    document.querySelectorAll(".skill-card").forEach(initCard);
  }

  /**
   * Initialize a single skill card: start countdown if active, wire up buttons.
   */
  function initCard(card) {
    // Read data attributes set by the server-rendered template
    const skillId = card.dataset.skillId;
    const remaining = parseInt(card.dataset.remaining, 10);
    const activeSince = card.dataset.activeSince;
    const display = card.querySelector(".timer-display");

    if (activeSince) {
      // Timer is running on the server — start the client-side countdown
      setActiveTimer(skillId, activeSince);
      startCountdown(skillId, activeSince, remaining, display);
    } else {
      // Timer is not running — show the static remaining time
      clearActiveTimer(skillId);
      display.textContent = formatCountdown(remaining);
    }

    // Bind button click handlers — use the JSON API to avoid full page reloads
    const startBtn = card.querySelector(".btn-start");
    const stopBtn = card.querySelector(".btn-stop");

    if (startBtn) {
      startBtn.addEventListener("click", async (e) => {
        e.preventDefault();
        // Tell the server to start the timer
        const resp = await fetch(`/api/skills/${skillId}/start`, {
          method: "POST",
        });
        if (resp.ok) {
          const data = await resp.json();
          // Persist the start time locally and reload to update button state
          setActiveTimer(skillId, data.active_since);
          location.reload();
        }
      });
    }

    if (stopBtn) {
      stopBtn.addEventListener("click", async (e) => {
        e.preventDefault();
        // Tell the server to stop the timer and record the session
        const resp = await fetch(`/api/skills/${skillId}/stop`, {
          method: "POST",
        });
        if (resp.ok) {
          // Clear local state and reload to show updated session log
          clearActiveTimer(skillId);
          location.reload();
        }
      });
    }
  }

  /**
   * Run a live countdown that ticks every second, updating the display element.
   * Automatically stops the timer on the server when remaining time hits zero.
   */
  function startCountdown(skillId, activeSinceIso, remainingAtLoad, display) {
    // Parse the server-provided start time to calculate elapsed time client-side
    const startTime = new Date(activeSinceIso).getTime();

    function tick() {
      const now = Date.now();
      // Calculate how many seconds have passed since the timer was started
      const elapsedSinceStart = Math.floor((now - startTime) / 1000);
      // Subtract from the remaining budget at page load time
      const currentRemaining = remainingAtLoad - elapsedSinceStart;

      if (currentRemaining <= 0) {
        // Target reached — show zero and auto-stop the timer on the server
        display.textContent = "00:00:00";
        display.classList.add("timer-done");
        fetch(`/api/skills/${skillId}/stop`, { method: "POST" }).then(() => {
          clearActiveTimer(skillId);
          location.reload();
        });
        return;
      }

      // Update the countdown display and schedule the next tick
      display.textContent = formatCountdown(currentRemaining);
      display.classList.add("timer-active");
      // Use requestAnimationFrame + setTimeout for smooth, battery-friendly ticking
      requestAnimationFrame(() => setTimeout(tick, 1000));
    }

    tick();
  }

  // Initialize all cards once the DOM is ready
  document.addEventListener("DOMContentLoaded", initCards);
})();
