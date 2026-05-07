/* h2t-editorial deck navigation.
 * Per R2b plan §10.1. Inlined verbatim into the inline script tag by the
 * assembler (single-file output contract); never loaded externally.
 *
 * Behavior is identical to R2a terminal deck nav (the contract is
 * profile-agnostic): keyboard / touch / hash sync / counter+progress
 * update / window.showSlide handle for deterministic screenshot tooling.
 * Mobile is CSS-only — viewport branching of any kind is forbidden by
 * the R2b mobile contract; the script does no media-query reads.
 */
(function () {
  var slides      = Array.prototype.slice.call(document.querySelectorAll('.slide'));
  var total       = slides.length;
  var progressBar = document.getElementById('progress-bar');
  var cntCurrent  = document.getElementById('cnt-current');
  var cntTotal    = document.getElementById('cnt-total');
  var btnPrev     = document.getElementById('btn-prev');
  var btnNext     = document.getElementById('btn-next');

  var current     = 0;
  var touching    = false;
  var touchStartX = 0;
  var touchStartY = 0;

  if (cntTotal) {
    // System B (rejuve-pitch-deck canonical): no zero-pad. Counter renders
    // "1 / 15", not "01 / 15". The `__SLOT_TOTAL_PADDED__` SSR value is
    // overwritten here at init.
    cntTotal.textContent = String(total);
  }

  function fmt(n) {
    return String(n + 1);
  }

  function clamp(idx) {
    if (idx < 0) return 0;
    if (idx >= total) return total - 1;
    return idx;
  }

  function showSlide(idx) {
    if (total === 0) return;
    idx = clamp(idx);
    if (slides[current]) slides[current].classList.remove('active');
    current = idx;
    slides[current].classList.add('active');

    // Progress: merkazim formula — first slide already shows >0% (more
    // intuitive than the pos-sprint normalized 0..100 over (total-1)).
    if (progressBar) {
      var pct = total === 0 ? 0 : ((current + 1) / total) * 100;
      progressBar.style.width = pct + '%';
    }
    if (cntCurrent) cntCurrent.textContent = fmt(current);

    // Optional nav button disabled state at edges.
    if (btnPrev) btnPrev.classList.toggle('disabled', current === 0);
    if (btnNext) btnNext.classList.toggle('disabled', current === total - 1);

    // Hash sync — deep-link to slide index (1-based, #1..#N).
    try {
      history.replaceState(null, '', '#' + (current + 1));
    } catch (err) { /* file:// or sandboxed contexts: ignore */ }
  }

  function next() { showSlide(current + 1); }
  function prev() { showSlide(current - 1); }

  document.addEventListener('keydown', function (e) {
    switch (e.key) {
      case 'ArrowRight':
      case 'ArrowDown':
      case ' ':
      case 'Enter':
        e.preventDefault();
        next();
        break;
      case 'ArrowLeft':
      case 'ArrowUp':
      case 'Backspace':
        e.preventDefault();
        prev();
        break;
      case 'Home':
        e.preventDefault();
        showSlide(0);
        break;
      case 'End':
        e.preventDefault();
        showSlide(total - 1);
        break;
    }
  });

  document.addEventListener('touchstart', function (e) {
    touching    = true;
    touchStartX = e.touches[0].clientX;
    touchStartY = e.touches[0].clientY;
  }, { passive: true });

  document.addEventListener('touchend', function (e) {
    if (!touching) return;
    touching = false;
    var dx = e.changedTouches[0].clientX - touchStartX;
    var dy = e.changedTouches[0].clientY - touchStartY;
    // Horizontal swipe threshold: >40px AND dominant over vertical motion.
    if (Math.abs(dx) > 40 && Math.abs(dx) > Math.abs(dy) * 1.5) {
      if (dx < 0) next();
      else        prev();
    }
  }, { passive: true });

  if (btnPrev) {
    btnPrev.addEventListener('click', function (e) { e.preventDefault(); prev(); });
  }
  if (btnNext) {
    btnNext.addEventListener('click', function (e) { e.preventDefault(); next(); });
  }

  // Init: honour incoming hash (#1..#N), else start at slide 0.
  var startIdx = 0;
  if (location.hash) {
    var parsed = parseInt(location.hash.replace('#', ''), 10);
    if (!isNaN(parsed)) startIdx = clamp(parsed - 1);
  }
  showSlide(startIdx);

  // Expose for deterministic tooling (deck-screenshot-all.py).
  window.showSlide = showSlide;
})();
