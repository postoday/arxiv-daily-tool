(() => {
  // ---------- Mini calendar ----------
  const calRoot = document.getElementById('mini-cal');
  const calBtn = document.getElementById('cal-toggle');
  if (calRoot && calBtn) {
    // Toggle open/close
    calBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      calRoot.classList.toggle('open');
    });
    // Close when clicking outside
    document.addEventListener('click', (e) => {
      if (!calRoot.contains(e.target) && e.target !== calBtn && !calBtn.contains(e.target)) {
        calRoot.classList.remove('open');
      }
    });

    const dates = window.__archiveDates || [];
    const cur = window.__currentDate || '';
    const pfx = window.__assetPrefix ?? '';
    const dateSet = new Set(dates);
    const ref = cur ? new Date(cur + 'T00:00:00') : new Date();
    let vY = ref.getFullYear();
    let vM = ref.getMonth();

    const MO = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    const DOW = ['Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa', 'Su'];

    function drawCalendar() {
      const first = new Date(vY, vM, 1);
      const days = new Date(vY, vM + 1, 0).getDate();
      const offset = (first.getDay() + 6) % 7;

      let html = '<div class="cal-head">'
        + '<button class="cal-nav" data-d="-1" type="button">\u2039</button>'
        + '<span class="cal-title">' + MO[vM] + ' ' + vY + '</span>'
        + '<button class="cal-nav" data-d="1" type="button">\u203A</button></div>'
        + '<div class="cal-grid">'
        + DOW.map((d) => '<span class="cal-dow">' + d + '</span>').join('');

      for (let i = 0; i < offset; i++) html += '<span class="cal-day"></span>';

      for (let d = 1; d <= days; d++) {
        const ds = vY + '-' + String(vM + 1).padStart(2, '0') + '-' + String(d).padStart(2, '0');
        const avail = dateSet.has(ds);
        const active = ds === cur;
        if (avail) {
          html += '<a class="cal-day has-data' + (active ? ' active' : '') + '" href="' + pfx + 'archive/' + ds + '.html">' + d + '</a>';
        } else {
          html += '<span class="cal-day">' + d + '</span>';
        }
      }
      html += '</div>';
      calRoot.innerHTML = html;

      calRoot.querySelectorAll('.cal-nav').forEach((button) => {
        button.addEventListener('click', (e) => {
          e.stopPropagation();
          vM += parseInt(button.dataset.d, 10);
          if (vM < 0) { vM = 11; vY--; }
          if (vM > 11) { vM = 0; vY++; }
          drawCalendar();
        });
      });
    }
    drawCalendar();

    // Prev / next date navigation
    const sorted = [...dates].sort();
    const idx = sorted.indexOf(cur);
    const prevBtn = document.getElementById('date-prev');
    const nextBtn = document.getElementById('date-next');
    if (prevBtn) {
      if (idx > 0) prevBtn.href = pfx + 'archive/' + sorted[idx - 1] + '.html';
      else prevBtn.classList.add('disabled');
    }
    if (nextBtn) {
      if (idx >= 0 && idx < sorted.length - 1) nextBtn.href = pfx + 'archive/' + sorted[idx + 1] + '.html';
      else nextBtn.classList.add('disabled');
    }
  }

  // ---------- Abstract expand / collapse ----------
  const abstractToggles = Array.from(document.querySelectorAll('.abstract-toggle'));

  function refreshAbstractToggles(root = document) {
    root.querySelectorAll('.paper-abstract').forEach((abstract) => {
      const toggle = abstract.nextElementSibling;
      if (!toggle || !toggle.classList.contains('abstract-toggle')) return;
      if (!abstract.offsetParent || abstract.classList.contains('expanded')) return;
      toggle.classList.toggle('is-hidden', abstract.scrollHeight <= abstract.clientHeight + 2);
    });
  }

  abstractToggles.forEach((toggle) => {
    toggle.addEventListener('click', () => {
      const abstract = toggle.previousElementSibling;
      if (!abstract || !abstract.classList.contains('paper-abstract')) return;
      const expanded = abstract.classList.toggle('expanded');
      toggle.setAttribute('aria-expanded', expanded ? 'true' : 'false');
      toggle.textContent = expanded ? 'Collapse Abstract' : 'Expand Abstract';
    });
  });

  // ---------- Paper filter ----------
  const searchInput = document.getElementById('search');
  const chipsRoot = document.getElementById('chips');
  const countBadge = document.getElementById('count-badge');
  const paperList = document.getElementById('paper-list');
  const controls = document.querySelector('.controls');
  const selectedPanel = document.getElementById('selected-panel');
  const papers = Array.from(document.querySelectorAll('.paper'));

  let activeCat = chipsRoot?.querySelector('.tab.active')?.dataset?.cat || '';

  const paperIndex = papers.map((el) => ({
    el,
    cats: (el.dataset.cats || '').split(',').map((cat) => cat.trim()).filter(Boolean),
    text: (el.textContent || '').toLowerCase(),
  }));

  function updateCount() {
    const visible = paperIndex.filter((p) => !p.el.classList.contains('hidden')).length;
    if (countBadge) countBadge.textContent = visible + (visible === 1 ? ' paper' : ' papers');
  }

  function applyFilter() {
    const q = (searchInput?.value || '').trim().toLowerCase();
    for (const p of paperIndex) {
      const matchCat = !activeCat || p.cats.includes(activeCat);
      const matchText = !q || p.text.includes(q);
      p.el.classList.toggle('hidden', !(matchCat && matchText));
    }
    updateCount();
    refreshAbstractToggles();
  }

  function showSelectedPanel(on) {
    paperList?.classList.toggle('hidden', on);
    controls?.classList.toggle('hidden', on);
    selectedPanel?.classList.toggle('hidden', !on);
    if (on && selectedPanel) refreshAbstractToggles(selectedPanel);
  }

  chipsRoot?.addEventListener('click', (e) => {
    const tab = e.target.closest('.tab');
    if (!tab) return;
    chipsRoot.querySelectorAll('.tab').forEach((t) => t.classList.remove('active'));
    tab.classList.add('active');
    activeCat = tab.dataset.cat;
    if (activeCat === '__selected__') {
      showSelectedPanel(true);
    } else {
      showSelectedPanel(false);
      applyFilter();
    }
  });

  searchInput?.addEventListener('input', applyFilter);

  if (papers.length) applyFilter();
  refreshAbstractToggles();
  window.addEventListener('resize', () => refreshAbstractToggles());
})();
