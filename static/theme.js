(function(){
  const valid=['light','midnight','nebula'];
  const select=document.getElementById('themeSelect');
  function apply(theme){
    if(!valid.includes(theme)) theme='light';
    document.body.classList.remove('dark','theme-midnight','theme-nebula');
    document.documentElement.dataset.theme=theme;
    if(theme==='midnight') document.body.classList.add('dark','theme-midnight');
    if(theme==='nebula') document.body.classList.add('dark','theme-nebula');
    localStorage.setItem('auravis-theme',theme);
    if(select) select.value=theme;
  }
  let saved=localStorage.getItem('auravis-theme')||'light';
  // migrate the older two-theme setting
  if(saved==='dark') saved='midnight';
  apply(saved);
  if(select) select.addEventListener('change',e=>apply(e.target.value));
})();
