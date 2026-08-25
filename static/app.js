(() => {
  const search = document.querySelector('#search');
  const city = document.querySelector('#city');
  const field = document.querySelector('#field');
  const beginner = document.querySelector('#beginner');
  const reset = document.querySelector('#reset-filters');
  const emptyReset = document.querySelector('#empty-reset');
  const rows = [...document.querySelectorAll('.opportunity-row')];
  const count = document.querySelector('#result-count');
  const label = document.querySelector('#result-label');
  const empty = document.querySelector('#empty-state');
  const list = document.querySelector('#opportunity-list');

  const hasFilters = () => Boolean(search.value.trim() || city.value !== 'All locations' || field.value !== 'All fields' || beginner.checked);

  const apply = () => {
    const query = search.value.trim().toLowerCase();
    let visible = 0;
    rows.forEach((row) => {
      const match = (!query || row.dataset.search.includes(query)) &&
        (city.value === 'All locations' || row.dataset.city === city.value) &&
        (field.value === 'All fields' || row.dataset.field === field.value) &&
        (!beginner.checked || row.dataset.beginner === 'true');
      row.hidden = !match;
      if (match) visible += 1;
    });
    count.textContent = visible;
    label.textContent = visible === 1 ? 'listing' : 'listings';
    empty.hidden = visible !== 0;
    list.hidden = visible === 0;
    reset.disabled = !hasFilters();
  };

  const clear = () => {
    search.value = '';
    city.value = 'All locations';
    field.value = 'All fields';
    beginner.checked = false;
    apply();
    search.focus();
  };

  [search, city, field].forEach((control) => control.addEventListener('input', apply));
  beginner.addEventListener('change', apply);
  reset.addEventListener('click', clear);
  emptyReset.addEventListener('click', clear);
})();
