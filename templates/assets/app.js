(() => {
  // ---------- Mini calendar ----------
  const calRoot = document.getElementById('mini-cal');
  const calBtn  = document.getElementById('cal-toggle');
  if (calRoot && calBtn) {
    // Toggle open/close
    calBtn.addEventListener('click', () => {
      calRoot.classList.toggle('open');
    });
    // Close when clicking outside
    document.addEventListener('click', (e) => {
      if (!calRoot.contains(e.target) && e.target !== calBtn && !calBtn.contains(e.target)) {
        calRoot.classList.remove('open');
      }
    });

    const dates = (window.__archiveDates || []);
    const cur   = window.__currentDate || '';
    const pfx   = window.__assetPrefix ?? '';
    const dateSet = new Set(dates);
    const ref = cur ? new Date(cur + 'T00:00:00') : new Date();
    let vY = ref.getFullYear(), vM = ref.getMonth();

    const MO = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
    const DOW = ['Mo','Tu','We','Th','Fr','Sa','Su'];

    function draw() {
      const first  = new Date(vY, vM, 1);
      const days   = new Date(vY, vM + 1, 0).getDate();
      const offset = (first.getDay() + 6) % 7;   // Mon=0

      let h = '<div class="cal-head">'
        + '<button class="cal-nav" data-d="-1">\u2039</button>'
        + '<span class="cal-title">' + MO[vM] + ' ' + vY + '</span>'
        + '<button class="cal-nav" data-d="1">\u203A</button></div>'
        + '<div class="cal-grid">'
        + DOW.map(d => '<span class="cal-dow">' + d + '</span>').join('');

      for (let i = 0; i < offset; i++) h += '<span class="cal-day"></span>';

      for (let d = 1; d <= days; d++) {
        const ds = vY + '-' + String(vM + 1).padStart(2, '0') + '-' + String(d).padStart(2, '0');
        const avail  = dateSet.has(ds);
        const active = ds === cur;
        if (avail) {
          const href = pfx + 'archive/' + ds + '.html';
          h += '<a class="cal-day has-data' + (active ? ' active' : '') + '" href="' + href + '">' + d + '</a>';
        } else {
          h += '<span class="cal-day">' + d + '</span>';
        }
      }
      h += '</div>';
      calRoot.innerHTML = h;

      calRoot.querySelectorAll('.cal-nav').forEach(b => {
        b.addEventListener('click', () => {
          vM += parseInt(b.dataset.d);
          if (vM < 0)  { vM = 11; vY--; }
          if (vM > 11) { vM = 0;  vY++; }
          draw();
        });
      });
    }
    draw();
  }

  // ---------- Paper filter ----------
  const searchInput = document.getElementById('search');
  const chipsRoot = document.getElementById('chips');
  const countBadge = document.getElementById('count-badge');
  const papers = Array.from(document.querySelectorAll('.paper'));
  if (!papers.length) return;

  // Single-select: always exactly one active tab
  let activeCat = chipsRoot?.querySelector('.tab.active')?.dataset?.cat || '';

  const paperIndex = papers.map(el => ({
    el,
    cats: (el.dataset.cats || '').split(',').filter(Boolean),
    text: (el.textContent || '').toLowerCase(),
  }));

  function updateCount() {
    const visible = paperIndex.filter(p => !p.el.classList.contains('hidden')).length;
    if (countBadge) countBadge.textContent = visible + ' papers';
  }

  function applyFilter() {
    const q = (searchInput?.value || '').trim().toLowerCase();
    for (const p of paperIndex) {
      const matchCat = !activeCat || p.cats.includes(activeCat);
      const matchText = !q || p.text.includes(q);
      p.el.classList.toggle('hidden', !(matchCat && matchText));
    }
    updateCount();
  }

  chipsRoot?.addEventListener('click', (e) => {
    const tab = e.target.closest('.tab');
    if (!tab) return;
    // Deselect all, activate clicked
    chipsRoot.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    tab.classList.add('active');
    activeCat = tab.dataset.cat;
    applyFilter();
  });

  searchInput?.addEventListener('input', applyFilter);

  // Init count
  applyFilter();
})();
