let ctx, dots = [], animId;
let _resizeHandler = null, _visibilityHandler = null;
const DOT_COUNT = 50, MAX_DIST = 120;

export function init(canvas) {
  ctx = canvas.getContext('2d');
  _resize(canvas);
  _createDots(canvas);
  _draw(canvas);
  _resizeHandler = () => { _resize(canvas); _createDots(canvas); };
  _visibilityHandler = () => {
    if (document.hidden) { cancelAnimationFrame(animId); animId = null; }
    else if (!animId) { _draw(canvas); }
  };
  window.addEventListener('resize', _resizeHandler);
  document.addEventListener('visibilitychange', _visibilityHandler);
}

export function destroy() {
  cancelAnimationFrame(animId);
  animId = null;
  dots = [];
  if (_resizeHandler) { window.removeEventListener('resize', _resizeHandler); _resizeHandler = null; }
  if (_visibilityHandler) { document.removeEventListener('visibilitychange', _visibilityHandler); _visibilityHandler = null; }
}

function _resize(canvas) {
  canvas.width = window.innerWidth;
  canvas.height = window.innerHeight;
  canvas.style.cssText = 'position:fixed;inset:0;z-index:-1;pointer-events:none;opacity:0.5;';
}

function _createDots(canvas) {
  dots = Array.from({ length: DOT_COUNT }, () => ({
    x: Math.random() * canvas.width,
    y: Math.random() * canvas.height,
    vx: (Math.random() - 0.5) * 0.12,
    vy: (Math.random() - 0.5) * 0.12,
    size: Math.random() < 0.5 ? 1 : 2,
    alpha: 0.03 + Math.random() * 0.21,
  }));
}

function _draw(canvas) {
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  dots.forEach(d => {
    d.x = (d.x + d.vx + canvas.width)  % canvas.width;
    d.y = (d.y + d.vy + canvas.height) % canvas.height;
  });
  for (let i = 0; i < dots.length; i++) {
    for (let j = i + 1; j < dots.length; j++) {
      const dx = dots[i].x - dots[j].x, dy = dots[i].y - dots[j].y;
      const dist = Math.sqrt(dx * dx + dy * dy);
      if (dist < MAX_DIST) {
        ctx.beginPath();
        ctx.moveTo(dots[i].x, dots[i].y);
        ctx.lineTo(dots[j].x, dots[j].y);
        ctx.strokeStyle = `rgba(214,48,48,${0.06 * (1 - dist / MAX_DIST)})`;
        ctx.lineWidth = 0.5;
        ctx.stroke();
      }
    }
  }
  dots.forEach(d => {
    ctx.fillStyle = `rgba(214,48,48,${d.alpha})`;
    ctx.fillRect(Math.round(d.x), Math.round(d.y), d.size, d.size);
  });
  animId = requestAnimationFrame(() => _draw(canvas));
}
