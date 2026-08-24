(() => {
  const search = document.querySelector('#search');
  const city = document.querySelector('#city');
  const field = document.querySelector('#field');
  const beginner = document.querySelector('#beginner');
  const cards = [...document.querySelectorAll('.opportunity-card')];
  const count = document.querySelector('#result-count');
  const empty = document.querySelector('#empty-state');
  const apply = () => {
    const q = search.value.trim().toLowerCase();
    let visible = 0;
    cards.forEach((card) => {
      const match = (!q || card.dataset.search.includes(q)) &&
        (city.value === 'All locations' || card.dataset.city === city.value) &&
        (field.value === 'All fields' || card.dataset.field === field.value) &&
        (!beginner.checked || card.dataset.beginner === 'true');
      card.hidden = !match;
      if (match) visible += 1;
    });
    count.textContent = visible;
    empty.hidden = visible !== 0;
  };
  [search, city, field].forEach((control) => control.addEventListener('input', apply));
  beginner.addEventListener('change', apply);
})();
