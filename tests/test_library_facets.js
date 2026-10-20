const fs = require('node:fs');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../app.js'), 'utf8');

function assert(condition, message) { if (!condition) throw new Error(message); }
function extractFunction(name) {
  const match = new RegExp(`^(?:async )?function ${name}\\(`, 'm').exec(source);
  if (!match) throw new Error(`Function ${name} not found in app.js`);
  const open = source.indexOf('{', match.index);
  let depth = 0;
  for (let i = open; i < source.length; i += 1) {
    if (source[i] === '{') depth += 1;
    if (source[i] === '}' && --depth === 0) return source.slice(match.index, i + 1);
  }
  throw new Error(`Unclosed function ${name}`);
}

(async () => {
  let passed = 0;
  {
    const fetchCalls = [];
    const elements = new Map();
    function getElement(selector) {
      if (!elements.has(selector)) {
        elements.set(selector, {
          value: '',
          innerHTML: '',
          options: [],
          textContent: '',
          disabled: false,
          attributes: new Map(),
          setAttribute(k, v) { this.attributes.set(k, v); }
        });
      }
      return elements.get(selector);
    }

    const areaFilter = getElement('#filter-area');
    const categoryFilter = getElement('#filter-category');

    const scope = {
      areaFilter,
      categoryFilter,
      escapeHtml: s => String(s),
      document: {
        querySelector(selector) { return getElement(selector); }
      },
      fetch: async url => {
        fetchCalls.push(url);
        if (url.startsWith('/api/facets')) {
          if (url.includes('area=ACADEMIA')) {
            return {
              ok: true,
              json: async () => ({
                areas: ['ACADEMIA', 'FUNCIONAL'],
                groups: [
                  { id: 'costas', name: 'Costas' },
                  { id: 'peito', name: 'Peito' },
                  { id: 'perna', name: 'Perna' }
                ]
              })
            };
          }
          if (url.includes('area=FUNCIONAL')) {
            return {
              ok: true,
              json: async () => ({
                areas: ['ACADEMIA', 'FUNCIONAL'],
                groups: [
                  { id: 'alongamento', name: 'Alongamento' },
                  { id: 'mobilidade', name: 'Mobilidade' },
                  { id: 'trx', name: 'TRX' }
                ]
              })
            };
          }
          return {
            ok: true,
            json: async () => ({
              areas: ['ACADEMIA', 'FUNCIONAL'],
              groups: []
            })
          };
        }
        if (url.startsWith('/api/library')) {
          return {
            ok: true,
            json: async () => ({
              total: 5,
              pages: 1,
              items: []
            })
          };
        }
        return { ok: true, json: async () => ({}) };
      },
      libraryPage: 1,
      libraryRequest: 0,
      sessionSelectionActive: false,
      workoutTargetDay: null
    };

    const funcs = [extractFunction('loadFacets'), extractFunction('loadLibrary')].join('\n');
    const api = new Function('scope', `with(scope){${funcs};return {loadFacets,loadLibrary}}`)(scope);

    // 1. Initial state (Todas as modalidades): second selector disabled with "Escolha uma modalidade"
    areaFilter.value = '';
    await api.loadFacets();
    assert(categoryFilter.disabled === true, 'categoryFilter must be disabled when Todas as modalidades is active');
    assert(categoryFilter.innerHTML.includes('Escolha uma modalidade'), 'categoryFilter placeholder should prompt for modality');
    assert(categoryFilter.value === '', 'categoryFilter value must be empty');
    await api.loadLibrary();
    const initialCall = fetchCalls[fetchCalls.length - 1];
    assert(!initialCall.includes('area=') && !initialCall.includes('category='), 'no area or category sent when Todas as modalidades is active');
    passed += 1;

    // 2. Select ACADEMIA: second selector enabled with "Todos os grupos" and only Academia options
    areaFilter.value = 'ACADEMIA';
    categoryFilter.value = '';
    await api.loadFacets();
    assert(categoryFilter.disabled === false, 'categoryFilter must be enabled when Academia is selected');
    assert(categoryFilter.innerHTML.includes('Todos os grupos'), 'categoryFilter default option for Academia should be Todos os grupos');
    assert(categoryFilter.innerHTML.includes('Costas') && categoryFilter.innerHTML.includes('Perna'), 'categoryFilter must list Academia groups');
    assert(!categoryFilter.innerHTML.includes('TRX'), 'categoryFilter must not list functional-only items in Academia');

    categoryFilter.value = 'costas';
    await api.loadLibrary();
    const academiaCall = fetchCalls[fetchCalls.length - 1];
    assert(academiaCall.includes('area=ACADEMIA') && academiaCall.includes('category=costas'), 'loadLibrary passes both Academia and Costas');
    passed += 1;

    // 3. Switch to FUNCIONAL: clears category, sets "Todas as categorias", shows only Funcional options
    areaFilter.value = 'FUNCIONAL';
    categoryFilter.value = '';
    await api.loadFacets();
    assert(categoryFilter.disabled === false, 'categoryFilter must be enabled when Funcional is selected');
    assert(categoryFilter.innerHTML.includes('Todas as categorias'), 'categoryFilter default option for Funcional should be Todas as categorias');
    assert(categoryFilter.innerHTML.includes('TRX') && categoryFilter.innerHTML.includes('Alongamento'), 'categoryFilter must list Funcional categories');
    assert(!categoryFilter.innerHTML.includes('Costas'), 'categoryFilter must not list non-functional items in this fixture');
    passed += 1;

    // 4. Switch back to Todas as modalidades: clears and disables second selector
    areaFilter.value = '';
    categoryFilter.value = '';
    await api.loadFacets();
    assert(categoryFilter.disabled === true, 'switching back to Todas as modalidades must disable categoryFilter');
    assert(categoryFilter.innerHTML.includes('Escolha uma modalidade'), 'categoryFilter must reset to Escolha uma modalidade');
    await api.loadLibrary();
    const resetCall = fetchCalls[fetchCalls.length - 1];
    assert(!resetCall.includes('area=') && !resetCall.includes('category='), 'library call has no area or category filters');
    passed += 1;
  }

  console.log(`Library facets tests: ${passed} passed`);
})().catch(error => { console.error(error); process.exitCode = 1; });
