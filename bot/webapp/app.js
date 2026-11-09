"use strict";
(() => {
  const copy = window.OQIBAT_COPY;
  const tg = window.Telegram && window.Telegram.WebApp;
  const byId = (id) => document.getElementById(id);
  const state = {tab:"profile", group:"", scope:"season", profile:null, version:0};
  const content = byId("content");
  function node(tag, text, className) {
    const item = document.createElement(tag);
    if (text !== undefined) item.textContent = text;
    if (className) item.className = className;
    return item;
  }
  function theme() {
    const values = tg ? tg.themeParams : {};
    const map = {bg_color:"--bg",secondary_bg_color:"--panel",text_color:"--text",hint_color:"--hint",button_color:"--accent",button_text_color:"--button-text"};
    Object.keys(map).forEach((key) => {
      if (/^#[0-9a-f]{6}$/i.test(values[key] || "")) document.documentElement.style.setProperty(map[key], values[key]);
    });
  }
  async function api(path) {
    try {
      const response = await fetch("/webapp/api/" + path, {headers:{"X-Telegram-Init-Data":tg.initData},cache:"no-store"});
      const data = await response.json();
      if (!response.ok) { const error = new Error(); error.publicMessage = data.error || copy.error; throw error; }
      return data;
    } catch (error) { if (!error.publicMessage) error.publicMessage = copy.error; throw error; }
  }
  function showError(text) { content.textContent = ""; content.appendChild(node("p",text,"error")); }
  function stat(value,label) {
    const item = node("div",undefined,"stat"); item.append(node("strong",value),node("span",label)); return item;
  }
  async function render() {
    const version = ++state.version;
    document.querySelectorAll("nav button").forEach((button) => button.setAttribute("aria-pressed",String(button.dataset.tab === state.tab)));
    content.textContent = "";
    if (state.tab === "rules") { content.append(node("h2",copy.rules_title),node("p",copy.rules,"rules")); return; }
    if (!tg || !tg.initData || !state.profile) { showError(copy.telegram_only); return; }
    if (state.tab === "profile") {
      content.append(node("h2",state.profile.name),node("p",state.profile.username ? "@"+state.profile.username : "","muted"));
      const stats = node("div",undefined,"stats");
      stats.append(stat(state.profile.points,copy.total_points),stat(state.profile.achievements,copy.achievement_count));
      content.appendChild(stats); return;
    }
    if (!state.group) { showError(copy.choose_group); return; }
    content.appendChild(node("p",copy.loading,"muted"));
    try {
      const query = "chat_id="+encodeURIComponent(state.group);
      const data = await api(state.tab === "leaderboard" ? "leaderboard?"+query+"&scope="+state.scope : "achievements?"+query);
      if (version !== state.version) return;
      content.textContent = "";
      const option = Array.from(byId("group").options).find((entry) => entry.value === String(data.group.id));
      if (option) option.textContent = data.group.title;
      content.appendChild(node("h2",data.group.title));
      if (state.tab === "leaderboard") {
        const scope = node("select"); scope.setAttribute("aria-label",copy.period);
        [["season",copy.season],["all",copy.all_time]].forEach(([value,label]) => { const option = node("option",label); option.value=value; option.selected=value===state.scope; scope.appendChild(option); });
        scope.addEventListener("change",() => { state.scope=scope.value; render(); });
        content.append(scope,node("p",data.label,"muted"));
        if (!data.items.length) content.appendChild(node("p",copy.no_scores,"muted"));
        const list = node("ol");
        data.items.forEach((entry,index) => { const row=node("li"); row.append(node("span",String(index+1),"rank"),node("span",entry.name,"name"),node("span",String(entry.points)+" "+copy.points,"score")); list.appendChild(row); });
        content.appendChild(list);
      } else {
        const list = node("ul");
        data.items.forEach((entry) => { const row=node("li",undefined,entry.unlocked_at ? "earned" : "locked"); row.append(node("span",entry.unlocked_at ? "✓" : "○"),node("span",entry.label,"name")); list.appendChild(row); });
        content.appendChild(list);
      }
    } catch (error) { if (version === state.version) showError(error.publicMessage || copy.error); }
  }
  byId("title").textContent=copy.title;
  byId("tagline").textContent=copy.tagline;
  byId("read-only").textContent=copy.read_only;
  byId("group-label").textContent=copy.group;
  byId("group-hint").textContent=copy.group_hint;
  byId("refresh").textContent=copy.refresh;
  byId("privacy-note").textContent=copy.privacy;
  [["profile",copy.profile],["leaderboard",copy.leaderboard],["achievements",copy.achievements],["rules",copy.rules_title]].forEach(([tab,label]) => {
    const button=node("button",label); button.type="button"; button.dataset.tab=tab;
    button.addEventListener("click",() => {state.tab=tab;render();}); byId("tabs").appendChild(button);
  });
  byId("group").addEventListener("change",() => {state.group=byId("group").value;render();});
  async function boot() {
    if (!tg || !tg.initData) { render(); return; }
    byId("refresh").disabled=true;
    try {
      state.profile=await api("profile");
      const start = tg.initDataUnsafe && tg.initDataUnsafe.start_param;
      if (!state.group && /^-[0-9]{1,19}$/.test(start || "")) state.group=start;
      const groups=state.profile.groups.slice();
      if (state.group && !groups.some((group) => String(group.id)===state.group)) groups.unshift({id:state.group,title:copy.link_group});
      byId("group").textContent="";
      groups.forEach((group) => {const option=node("option",group.title); option.value=String(group.id); byId("group").appendChild(option);});
      if (!state.group && groups.length) state.group=String(groups[0].id);
      byId("group").value=state.group;
      if (start && state.tab === "profile") state.tab="leaderboard";
      await render();
    } catch(error) {showError(error.publicMessage || copy.error);}
    finally {byId("refresh").disabled=false;}
  }
  byId("refresh").addEventListener("click",boot);
  theme();
  if (tg) {tg.ready();tg.expand();tg.onEvent("themeChanged",theme);}
  boot();
})();
