/* h2t-terminal deck navigation.
 * Per design system §Navigation. Inlined verbatim into the inline script tag
 * by the assembler (single-file output contract); never loaded externally.
 *
 * Surface:
 *   - Keyboard: ArrowRight/ArrowDown/Space/Enter -> next;
 *               ArrowLeft/ArrowUp/Backspace -> prev; Home -> first; End -> last.
 *   - Touch: horizontal swipe > 40px (and dominant over vertical) -> next/prev.
 *   - Frame: progress = ((current+1)/total)*100 (merkazim formula); counter
 *     shows zero-padded 'NN / NN'.
 *   - Hash: read on init (#3 -> slide index 2), replaceState on each change.
 *   - Optional prev/next buttons: #btn-prev / #btn-next (rendered when
 *     recipe.nav_buttons is true); .disabled toggled at edges.
 *   - The showSlide(idx) handle is exposed on the global object for
 *     deterministic screenshot tooling (T12 deck-screenshot-all.py); avoids
 *     keyboard-fallback fragility in headless browsers. Goldens used
 *     IIFE-local scope; we deliberately leak the handle while keeping
 *     internal state private.
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
    cntTotal.textContent = String(total).padStart(2, '0');
  }

  function pad(n) {
    return String(n + 1).padStart(2, '0');
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

    // Progress: merkazim formula — first slide already shows >0% (more intuitive
    // than the pos-sprint normalized 0..100 over (total-1)).
    if (progressBar) {
      var pct = total === 0 ? 0 : ((current + 1) / total) * 100;
      progressBar.style.width = pct + '%';
    }
    if (cntCurrent) cntCurrent.textContent = pad(current);

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

  // Expose for deterministic tooling (T12 deck-screenshot-all.py).
  window.showSlide = showSlide;
})();
