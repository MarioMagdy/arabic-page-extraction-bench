// Scroll-driven scrollytelling v2 opening behaviour for the benchmark report.
(function() {
  'use strict';
  document.documentElement.classList.add('js');

  const story = document.getElementById('story');
  const figure = document.getElementById('storyFigure');
  if (!story || !figure) return;

  const steps = Array.from(story.querySelectorAll('.step'));
  if (!steps.length) return;

  const heroHint = story.querySelector('.scroll-hint');
  const heroContent = story.querySelector('.step-hero .step-content');
  const heroFrame = document.getElementById('figPageFrame');
  const rail = document.getElementById('storyRail');
  const railDots = rail ? Array.from(rail.querySelectorAll('.rail-dot')) : [];

  const boxGroups = Array.from(story.querySelectorAll('.fig-box-g'));
  const boxRects = Array.from(story.querySelectorAll('.fig-box-rect'));
  const boxTabs = Array.from(story.querySelectorAll('.fig-box-tab'));
  const defectCounter = document.getElementById('defectCounter');
  const defectTrack = document.getElementById('defectTrack');

  const deckCards = Array.from(story.querySelectorAll('.deck-card'));
  const chips = Array.from(story.querySelectorAll('.story-chip'));
  const goldCards = deckCards.filter(c => c.classList.contains('is-gold'))
    .sort((a, b) => +(a.getAttribute('data-gold-idx') || 0) - +(b.getAttribute('data-gold-idx') || 0));

  const chartSvg = document.getElementById('storyChartSvg');
  const chartAxes = chartSvg ? chartSvg.querySelector('.chart-axes-grid') : null;
  const chartPoints = chartSvg ? Array.from(chartSvg.querySelectorAll('.chart-point-group')) : [];
  const chartLabels = chartSvg ? Array.from(chartSvg.querySelectorAll('.point-name-label')) : [];
  const chartLegendDesktop = chartSvg ? chartSvg.querySelector('.chart-legend-desktop') : null;
  const chartLegendRows = chartSvg ? Array.from(chartSvg.querySelectorAll('.chart-legend-row')) : [];
  const priceRatio = document.getElementById('storyPriceRatio');
  const costBars = document.getElementById('figCostBars');
  const costBarRows = costBars ? Array.from(costBars.querySelectorAll('.cost-bar-row')) : [];

  let targetZoomVb = [111.1, 23.8, 631.0, 85.0];
  if (chartSvg && chartSvg.getAttribute('data-zoom-target')) {
    const p = chartSvg.getAttribute('data-zoom-target').split(/\s+/).map(Number);
    if (p.length === 4 && !p.some(isNaN)) targetZoomVb = p;
  }

  const thinkOnPrice = document.getElementById('thinkOnPrice');
  const thinkOffPrice = document.getElementById('thinkOffPrice');
  const thinkFillOn = document.getElementById('thinkFillOn');
  const thinkSegTokens = document.getElementById('thinkSegTokens');
  const thinkFillOff = document.getElementById('thinkFillOff');

  let cachedStepRects = [], stepBoundaries = [];
  let winHeight = window.innerHeight, winWidth = window.innerWidth;
  let currentBeat = -1, storyBottom = 0;

  const ease = p => 1 - Math.pow(1 - Math.max(0, Math.min(1, p)), 3);
  const getBaseVb = () => winWidth < 900 ? [0, 0, 740, 760] : [0, 0, 1000, 620];

  function updateRects() {
    winHeight = window.innerHeight; winWidth = window.innerWidth;
    const scrollY = window.scrollY;
    cachedStepRects = steps.map(el => {
      const r = el.getBoundingClientRect(), top = r.top + scrollY;
      return { top, bottom: top + r.height, height: r.height };
    });
    storyBottom = story.getBoundingClientRect().bottom + scrollY;
    const rLine = 0.5 * winHeight;
    stepBoundaries = [0];
    for (let i = 1; i < cachedStepRects.length; i++) {
      stepBoundaries.push(Math.max(stepBoundaries[i - 1] + 20, cachedStepRects[i].top - rLine));
    }
    const last = cachedStepRects[cachedStepRects.length - 1];
    stepBoundaries.push(Math.max(stepBoundaries[stepBoundaries.length - 1] + 20, last.bottom - rLine));
  }
  updateRects();
  window.addEventListener('resize', updateRects, { passive: true });
  window.addEventListener('load', updateRects);

  window.__story = { beat: 0, p: 0, t: 0 };

  railDots.forEach(dot => {
    dot.addEventListener('click', () => {
      const idx = parseInt(dot.getAttribute('data-beat'), 10);
      if (steps[idx]) steps[idx].scrollIntoView({ behavior: 'smooth', block: 'center' });
    });
  });

  function updateBeat0(p, scrollY) {
    if (heroHint) heroHint.style.opacity = scrollY > 40 ? '0' : '1';
    if (heroContent) heroContent.style.opacity = String(Math.max(0, 1 - p * 1.6));
    if (heroFrame) {
      if (winWidth >= 900) {
        heroFrame.style.transform = `translateX(${((1 - p) * 26).toFixed(2)}vw) scale(${(1.22 - 0.22 * p).toFixed(3)})`;
      } else {
        heroFrame.style.transform = `scale(${(1.08 - 0.08 * p).toFixed(3)})`;
      }
    }
  }

  function updateBeat2(p) {
    let latestIdx = -1;
    for (let i = 7; i >= 0; i--) { if (p >= i / 8) { latestIdx = i; break; } }
    boxRects.forEach((rect, i) => {
      const perim = parseFloat(rect.getAttribute('data-perim') || '1000');
      const boxSlice = Math.max(0, Math.min(1, 8 * p - i));
      rect.style.strokeDashoffset = ((1 - boxSlice) * perim).toFixed(1);
      const gOp = p >= (i + 1) / 8 ? 0.7 : (p >= i / 8 ? 1.0 : 0);
      if (boxGroups[i]) {
        boxGroups[i].style.opacity = String(gOp);
        boxGroups[i].classList.toggle('latest', i === latestIdx);
      }
      if (boxTabs[i]) {
        const tOp = p >= (i + 1) / 8 ? 0.7 : (boxSlice >= 0.7 ? (boxSlice - 0.7) / 0.3 : 0);
        boxTabs[i].style.opacity = tOp.toFixed(2);
      }
    });
  }

  function updateBeat3(p) {
    const pg = Math.min(1, p / 0.5);
    if (boxGroups[0]) {
      boxGroups[0].style.transform = `translateY(${(pg * 300).toFixed(1)}px)`;
      if (boxRects[0]) { boxRects[0].style.stroke = pg > 0.05 ? 'var(--accent)' : ''; boxRects[0].style.fill = pg > 0.05 ? 'var(--accent)' : ''; }
      const t = boxTabs[0]?.querySelector('.fig-box-tab-bg'); if (t) t.style.fill = pg > 0.05 ? 'var(--accent)' : '';
    }
    if (boxGroups[7]) {
      boxGroups[7].style.transform = `translateY(${(-pg * 820).toFixed(1)}px)`;
      if (boxRects[7]) { boxRects[7].style.stroke = pg > 0.05 ? 'var(--accent)' : ''; boxRects[7].style.fill = pg > 0.05 ? 'var(--accent)' : ''; }
      const t = boxTabs[7]?.querySelector('.fig-box-tab-bg'); if (t) t.style.fill = pg > 0.05 ? 'var(--accent)' : '';
    }
    const pDef = Math.max(0, Math.min(1, (p - 0.5) / 0.5));
    if (defectCounter) {
      const tgt = parseInt(defectCounter.getAttribute('data-target') || '365', 10);
      defectCounter.textContent = String(Math.round(pDef * tgt));
    }
    if (defectTrack) defectTrack.style.clipPath = `inset(0 ${((1 - pDef) * 100).toFixed(1)}% 0 0)`;
  }

  function updateBeat4(p) {
    const sf = winWidth < 900 ? 0.55 : 1.0;
    deckCards.forEach((c, k) => {
      const d = k - 9.5;
      c.style.transform = `translate(${(d * 15.5 * sf * p).toFixed(1)}px, ${((d * d * 0.85 * sf - 10) * p).toFixed(1)}px) rotate(${(d * 1.7 * p).toFixed(2)}deg)`;
      c.style.opacity = '1'; c.style.boxShadow = '';
      const ch = c.querySelector('.gold-check'); if (ch) ch.style.opacity = '0';
    });
    chips.forEach((ch, i) => {
      const s = Math.max(0, Math.min(1, (p - (0.4 + i * 0.05)) / 0.05));
      ch.style.opacity = s.toFixed(3);
      ch.style.transform = `translateX(${((1 - s) * 24).toFixed(1)}px)`;
    });
  }

  function updateBeat5(p) {
    const sf = winWidth < 900 ? 0.55 : 1.0, nG = goldCards.length;
    goldCards.forEach((c, j) => {
      const k = parseInt(c.getAttribute('data-idx') || '0', 10), d = k - 9.5;
      const bx = d * 15.5 * sf, by = d * d * 0.85 * sf - 10, rot = d * 1.7;
      const s = Math.max(0, Math.min(1, nG * p - j)), lift = -34 * s * sf;
      c.style.transform = `translate(${bx.toFixed(1)}px, ${(by + lift).toFixed(1)}px) rotate(${rot.toFixed(2)}deg) scale(${(1 + 0.15 * s).toFixed(3)})`;
      c.style.opacity = '1'; c.style.zIndex = s > 0 ? '15' : '2';
      c.style.boxShadow = s > 0 ? `0 0 0 2px var(--good), ${(3 * s).toFixed(1)}px ${(3 * s).toFixed(1)}px 0 0 var(--good)` : '';
      const ch = c.querySelector('.gold-check');
      if (ch) {
        const cv = s >= 0.7 ? (s - 0.7) / 0.3 : 0;
        ch.style.opacity = cv.toFixed(2);
        ch.style.transform = `scale(${(0.4 + 0.6 * cv).toFixed(2)})`;
      }
    });
    const dim = Math.max(0.4, 1 - 0.6 * p).toFixed(2);
    deckCards.forEach(c => { if (!c.classList.contains('is-gold')) c.style.opacity = dim; });
    const cr = Math.max(0.3, 1 - 0.7 * p).toFixed(2);
    chips.forEach(ch => { ch.style.opacity = cr; ch.style.transform = 'none'; });
  }

  function updateBeat6(p) {
    if (!chartSvg) return;
    chartSvg.setAttribute('viewBox', getBaseVb().join(' '));
    if (chartAxes) chartAxes.style.opacity = String(Math.min(1, p / 0.15));
    const nPts = chartPoints.length || 11, dPt = 0.60 / nPts;
    chartPoints.forEach((pt, i) => {
      const pS = 0.15 + i * dPt, pM = pS + 0.55 * dPt, pE = pS + dPt;
      const wh = pt.querySelector('.point-whisker'), caps = pt.querySelectorAll('.point-cap');
      if (p < pS) {
        pt.style.opacity = '0'; pt.style.transform = 'translateY(-60px)';
        if (wh) wh.style.transform = 'scaleY(0)'; caps.forEach(c => c.style.opacity = '0');
      } else if (p < pM) {
        const f = ease((p - pS) / (pM - pS));
        pt.style.opacity = f.toFixed(2); pt.style.transform = `translateY(${((1 - f) * -60).toFixed(1)}px)`;
        if (wh) wh.style.transform = 'scaleY(0)'; caps.forEach(c => c.style.opacity = '0');
      } else if (p < pE) {
        pt.style.opacity = '1'; pt.style.transform = 'none';
        const w = (p - pM) / (pE - pM);
        if (wh) wh.style.transform = `scaleY(${w.toFixed(2)})`; caps.forEach(c => c.style.opacity = w.toFixed(2));
      } else {
        pt.style.opacity = '1'; pt.style.transform = 'none';
        if (wh) wh.style.transform = 'scaleY(1)'; caps.forEach(c => c.style.opacity = '1');
      }
    });
    chartLabels.forEach(l => l.style.opacity = '0');
    const nR = chartLegendRows.length || 11, dR = 0.25 / nR;
    chartLegendRows.forEach((r, i) => {
      const v = Math.max(0, Math.min(1, (p - (0.75 + i * dR)) / dR));
      r.style.opacity = v.toFixed(2); r.style.transform = `translateX(${((1 - v) * 16).toFixed(1)}px)`;
    });
    if (chartLegendDesktop) chartLegendDesktop.style.opacity = '1';
  }

  function fitAspect(vb, base) {
    // Expand the target box to the base viewBox's aspect ratio, centred, so the zoom is a true
    // magnification: a box of the wrong shape gets letterboxed by preserveAspectRatio="meet".
    const ar = base[2] / base[3];
    let [x, y, w, h] = vb;
    if (w / h > ar) { const nh = w / ar; y -= (nh - h) / 2; h = nh; }
    else { const nw = h * ar; x -= (nw - w) / 2; w = nw; }
    // never look past the chart's left or right edge; vertical overshoot is fine (card background)
    x = Math.max(base[0], Math.min(x, base[0] + base[2] - w));
    return [x, y, w, h];
  }

  function updateBeat7(p) {
    if (!chartSvg) return;
    const baseVb = getBaseVb(), pZoom = Math.min(1, p / 0.5), e = ease(pZoom);
    const tz = fitAspect(targetZoomVb, baseVb);
    const vx = baseVb[0] + e * (tz[0] - baseVb[0]);
    const vy = baseVb[1] + e * (tz[1] - baseVb[1]);
    const vw = baseVb[2] + e * (tz[2] - baseVb[2]);
    const vh = baseVb[3] + e * (tz[3] - baseVb[3]);
    chartSvg.setAttribute('viewBox', `${vx.toFixed(1)} ${vy.toFixed(1)} ${vw.toFixed(1)} ${vh.toFixed(1)}`);
    // the bars under the chart name the six in colour; point labels only collide at this zoom
    chartLabels.forEach(l => l.style.opacity = '0');
    chartPoints.forEach(pt => {
      if (pt.getAttribute('data-ok') === '0') {
        pt.style.opacity = (1 - e).toFixed(2);
      } else {
        pt.style.opacity = '1'; pt.style.transform = 'none';
        const wh = pt.querySelector('.point-whisker'); if (wh) wh.style.transform = 'scaleY(1)';
        pt.querySelectorAll('.point-cap').forEach(c => c.style.opacity = '1');
      }
    });
    if (chartLegendDesktop) chartLegendDesktop.style.opacity = (1 - e).toFixed(2);
    if (priceRatio) {
      const tgt = parseInt(priceRatio.getAttribute('data-target') || '22', 10);
      priceRatio.textContent = `${1 + Math.round(e * (tgt - 1))}×`;
    }
    const pBars = Math.max(0, Math.min(1, (p - 0.5) / 0.5));
    costBarRows.forEach(row => {
      const fill = row.querySelector('.cost-bar-fill'), val = row.querySelector('.cost-bar-val');
      const cost = parseFloat(row.getAttribute('data-cost') || '0');
      if (fill) { fill.style.transform = `scaleX(${pBars.toFixed(3)})`; fill.style.transformOrigin = 'left'; }
      if (val) val.textContent = `$${(pBars * cost).toFixed(2)}`;
    });
  }

  function updateBeat8(p) {
    const onTgt = parseFloat(thinkOnPrice?.getAttribute('data-target') || '3.31');
    const offTgt = parseFloat(thinkOffPrice?.getAttribute('data-target') || '1.27');
    if (thinkOnPrice) thinkOnPrice.textContent = `$${(p * onTgt).toFixed(2)}`;
    if (thinkOffPrice) thinkOffPrice.textContent = `$${(p * offTgt).toFixed(2)}`;
    if (thinkFillOn) { thinkFillOn.style.transform = `scaleX(${p.toFixed(3)})`; thinkFillOn.style.transformOrigin = 'left'; }
    if (thinkSegTokens) thinkSegTokens.style.width = `${(p * 74).toFixed(1)}%`;
    if (thinkFillOff) thinkFillOff.style.width = `${(p * (offTgt / onTgt) * 100).toFixed(1)}%`;
  }

  function setBeatStaticState(b) {
    if (heroFrame && b > 0) heroFrame.style.transform = 'none';
    if (heroContent && b > 0) heroContent.style.opacity = '0';
    if (b > 2) {
      boxRects.forEach((r, i) => { r.style.strokeDashoffset = '0'; if (boxGroups[i]) { boxGroups[i].style.opacity = '0.7'; boxGroups[i].classList.remove('latest'); } if (boxTabs[i]) boxTabs[i].style.opacity = '0.7'; });
    } else if (b < 2) {
      boxRects.forEach((r, i) => { r.style.strokeDashoffset = r.getAttribute('data-perim') || '1000'; if (boxGroups[i]) { boxGroups[i].style.opacity = '0'; boxGroups[i].classList.remove('latest'); } if (boxTabs[i]) boxTabs[i].style.opacity = '0'; });
    }
    if (b < 3) {
      if (boxGroups[0]) { boxGroups[0].style.transform = 'none'; if (boxRects[0]) { boxRects[0].style.stroke = ''; boxRects[0].style.fill = ''; } }
      if (boxGroups[7]) { boxGroups[7].style.transform = 'none'; if (boxRects[7]) { boxRects[7].style.stroke = ''; boxRects[7].style.fill = ''; } }
      if (defectCounter) defectCounter.textContent = '0';
      if (defectTrack) defectTrack.style.clipPath = 'inset(0 100% 0 0)';
    } else if (b > 3) {
      if (defectCounter) defectCounter.textContent = defectCounter.getAttribute('data-target') || '365';
      if (defectTrack) defectTrack.style.clipPath = 'inset(0 0 0 0)';
    }
    if (b > 4) chips.forEach(c => c.style.transform = 'none');
    if (b > 6) {
      chartPoints.forEach(pt => {
        pt.style.transform = 'none'; const wh = pt.querySelector('.point-whisker');
        if (wh) wh.style.transform = 'scaleY(1)'; pt.querySelectorAll('.point-cap').forEach(c => c.style.opacity = '1');
      });
      chartLegendRows.forEach(r => { r.style.opacity = '1'; r.style.transform = 'none'; });
    }
    if (b > 7) {
      costBarRows.forEach(r => {
        const f = r.querySelector('.cost-bar-fill'), v = r.querySelector('.cost-bar-val');
        if (f) f.style.transform = 'scaleX(1)'; if (v) v.textContent = `$${r.getAttribute('data-cost') || '0'}`;
      });
      if (priceRatio) priceRatio.textContent = `${priceRatio.getAttribute('data-target') || '22'}×`;
    } else if (b < 7) {
      if (chartSvg) chartSvg.setAttribute('viewBox', getBaseVb().join(' '));
      chartLabels.forEach(l => l.style.opacity = '0');
      if (chartLegendDesktop) chartLegendDesktop.style.opacity = '1';
      if (priceRatio) priceRatio.textContent = '1×';
      costBarRows.forEach(r => {
        const f = r.querySelector('.cost-bar-fill'), v = r.querySelector('.cost-bar-val');
        if (f) f.style.transform = 'scaleX(0)'; if (v) v.textContent = '$0.00';
      });
    }
    if (b > 8) updateBeat8(1); else if (b < 8) updateBeat8(0);
  }

  function setActiveBeat(beat) {
    if (beat === currentBeat) return;
    currentBeat = beat;
    figure.setAttribute('data-beat', String(beat));
    steps.forEach((s, i) => s.classList.toggle('active', i === beat));
    railDots.forEach(d => d.classList.toggle('active', +(d.getAttribute('data-beat') || -1) === beat));
    setBeatStaticState(beat);
  }

  function updateFrame() {
    const scrollY = window.scrollY, n = cachedStepRects.length;
    let beat = 0, p = 0;
    if (scrollY <= stepBoundaries[0]) {
      beat = 0; p = 0;
    } else if (scrollY >= stepBoundaries[stepBoundaries.length - 1]) {
      beat = n - 1; p = 1;
    } else {
      for (let i = 0; i < n; i++) {
        if (scrollY >= stepBoundaries[i] && scrollY < stepBoundaries[i + 1]) {
          beat = i;
          const span = stepBoundaries[i + 1] - stepBoundaries[i];
          p = span > 0 ? (scrollY - stepBoundaries[i]) / span : 0;
          break;
        }
      }
    }
    p = Math.max(0, Math.min(1, p));
    const t = beat + p;
    figure.style.setProperty('--p', p.toFixed(4));
    figure.style.setProperty('--t', t.toFixed(4));
    window.__story = { beat, p, t };

    if (beat !== currentBeat) setActiveBeat(beat);
    if (rail) rail.classList.toggle('past-story', scrollY > (storyBottom - winHeight));

    if (beat === 0) updateBeat0(p, scrollY);
    else if (beat === 1) updateBeat0(1, scrollY);
    else if (beat === 2) updateBeat2(p);
    else if (beat === 3) updateBeat3(p);
    else if (beat === 4) updateBeat4(p);
    else if (beat === 5) updateBeat5(p);
    else if (beat === 6) updateBeat6(p);
    else if (beat === 7) updateBeat7(p);
    else if (beat === 8) updateBeat8(p);
  }

  let ticking = false;
  window.addEventListener('scroll', () => {
    if (!ticking) {
      requestAnimationFrame(() => { updateFrame(); ticking = false; });
      ticking = true;
    }
  }, { passive: true });

  updateFrame();
})();
