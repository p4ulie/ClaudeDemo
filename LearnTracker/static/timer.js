/**
 * Client-side countdown timer for LearnTracker.
 * Uses localStorage to persist running timer state across page refreshes.
 */
(function () {
  "use strict";

  const STORAGE_KEY = "learntracker_active_timers";

  function getActiveTimers() {
    try {
      return JSON.parse(localStorage.getItem(STORAGE_KEY)) || {};
    } catch {
      return {};
    }
  }

  function setActiveTimer(skillId, startIso) {
    const timers = getActiveTimers();
    timers[skillId] = startIso;
    localStorage.setItem(STORAGE_KEY, JSON.stringify(timers));
  }

  function clearActiveTimer(skillId) {
    const timers = getActiveTimers();
    delete timers[skillId];
    localStorage.setItem(STORAGE_KEY, JSON.stringify(timers));
  }

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

  function initCards() {
    document.querySelectorAll(".skill-card").forEach(initCard);
  }

  function initCard(card) {
    const skillId = card.dataset.skillId;
    const remaining = parseInt(card.dataset.remaining, 10);
    const activeSince = card.dataset.activeSince;
    const display = card.querySelector(".timer-display");

    if (activeSince) {
      // Timer is running — start countdown
      setActiveTimer(skillId, activeSince);
      startCountdown(skillId, activeSince, remaining, display);
    } else {
      clearActiveTimer(skillId);
      display.textContent = formatCountdown(remaining);
    }

    // Button handlers — use API to avoid full page reload
    const startBtn = card.querySelector(".btn-start");
    const stopBtn = card.querySelector(".btn-stop");

    if (startBtn) {
      startBtn.addEventListener("click", async (e) => {
        e.preventDefault();
        const resp = await fetch(`/api/skills/${skillId}/start`, {
          method: "POST",
        });
        if (resp.ok) {
          const data = await resp.json();
          setActiveTimer(skillId, data.active_since);
          // Reload to update UI state (buttons, etc.)
          location.reload();
        }
      });
    }

    if (stopBtn) {
      stopBtn.addEventListener("click", async (e) => {
        e.preventDefault();
        const resp = await fetch(`/api/skills/${skillId}/stop`, {
          method: "POST",
        });
        if (resp.ok) {
          clearActiveTimer(skillId);
          location.reload();
        }
      });
    }
  }

  function startCountdown(skillId, activeSinceIso, remainingAtLoad, display) {
    const startTime = new Date(activeSinceIso).getTime();

    function tick() {
      const now = Date.now();
      const elapsedSinceStart = Math.floor((now - startTime) / 1000);
      const currentRemaining = remainingAtLoad - elapsedSinceStart;

      if (currentRemaining <= 0) {
        display.textContent = "00:00:00";
        display.classList.add("timer-done");
        // Auto-stop
        fetch(`/api/skills/${skillId}/stop`, { method: "POST" }).then(() => {
          clearActiveTimer(skillId);
          location.reload();
        });
        return;
      }

      display.textContent = formatCountdown(currentRemaining);
      display.classList.add("timer-active");
      requestAnimationFrame(() => setTimeout(tick, 1000));
    }

    tick();
  }

  document.addEventListener("DOMContentLoaded", initCards);
})();
