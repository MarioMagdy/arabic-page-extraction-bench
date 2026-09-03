// Scroll-driven opening behaviour for the benchmark report.
(function() {
  'use strict';
  document.documentElement.classList.add('js');

  const story = document.getElementById('story');
  if (!story) return;

  const figure = document.getElementById('storyFigure');
  if (!figure) return;

  const steps = Array.from(story.querySelectorAll('.step'));
  const heroHint = story.querySelector('.scroll-hint');
  const boxes = Array.from(story.querySelectorAll('.fig-box'));

  let cachedStepRects = [];
  let winHeight = window.innerHeight;
  let currentBeat = -1;

  function updateRects() {
    winHeight = window.innerHeight;
    const scrollY = window.scrollY;
    cachedStepRects = steps.map(function(el) {
      const rect = el.getBoundingClientRect();
      const top = rect.top + scrollY;
      const height = rect.height;
      return {
        top: top,
        bottom: top + height,
        height: height
      };
    });
  }

  updateRects();
  window.addEventListener('resize', updateRects, { passive: true });

  function getStepProgress(stepIdx, scrollY) {
    const rect = cachedStepRects[stepIdx];
    if (!rect) return 0;
    // 0...1 = step's top passing viewport 80% line to bottom passing 20% line
    const start = rect.top - 0.8 * winHeight;
    const end = rect.bottom - 0.2 * winHeight;
    const span = end - start;
    if (span <= 0) return 0;
    return Math.max(0, Math.min(1, (scrollY - start) / span));
  }

  function updateStep2Boxes() {
    if (currentBeat !== 2) return;
    const p = getStepProgress(2, window.scrollY);
    let latestIdx = -1;
    for (let i = 7; i >= 0; i--) {
      if (p >= i / 8) {
        latestIdx = i;
        break;
      }
    }
    boxes.forEach(function(box, i) {
      if (p >= i / 8) {
        box.classList.add('visible');
        box.classList.toggle('latest', i === latestIdx);
      } else {
        box.classList.remove('visible', 'latest');
      }
    });
  }

  function setActiveBeat(beat) {
    if (beat === currentBeat) return;
    currentBeat = beat;
    figure.setAttribute('data-beat', String(beat));
    steps.forEach(function(step, i) {
      step.classList.toggle('active', i === beat);
    });

    if (beat === 2) {
      updateStep2Boxes();
    } else if (beat > 2) {
      boxes.forEach(function(box) {
        box.classList.add('visible');
        box.classList.remove('latest');
      });
    } else {
      boxes.forEach(function(box) {
        box.classList.remove('visible', 'latest');
      });
    }
  }

  // IntersectionObserver to identify active step
  const observer = new IntersectionObserver(function(entries) {
    entries.forEach(function(entry) {
      if (entry.isIntersecting) {
        const idx = parseInt(entry.target.getAttribute('data-step'), 10);
        if (!isNaN(idx)) {
          setActiveBeat(idx);
        }
      }
    });
  }, {
    rootMargin: '-35% 0px -35% 0px',
    threshold: 0
  });

  steps.forEach(function(step) {
    observer.observe(step);
  });

  // Handle initial active beat on load
  const initialCenter = window.scrollY + winHeight * 0.5;
  let initialFound = false;
  for (let i = 0; i < cachedStepRects.length; i++) {
    if (initialCenter >= cachedStepRects[i].top && initialCenter <= cachedStepRects[i].bottom) {
      setActiveBeat(i);
      initialFound = true;
      break;
    }
  }
  if (!initialFound && steps.length > 0) {
    setActiveBeat(0);
  }

  // rAF-throttled scroll listener
  let ticking = false;
  function handleScroll() {
    const scrollY = window.scrollY;
    if (heroHint) {
      heroHint.style.opacity = scrollY > 40 ? '0' : '1';
    }
    if (currentBeat === 2) {
      updateStep2Boxes();
    }
  }

  window.addEventListener('scroll', function() {
    if (!ticking) {
      requestAnimationFrame(function() {
        handleScroll();
        ticking = false;
      });
      ticking = true;
    }
  }, { passive: true });

})();
