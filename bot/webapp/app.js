"use strict";
(() => {
  const copy = window.OQIBAT_COPY;
  const tg = window.Telegram && window.Telegram.WebApp;
  const byId = (id) => document.getElementById(id);
  const state = {tab:"profile", group:"", scope:"season", profile:null, version:0};
  const content = byId("content");
  let countdown = null;
  function node(tag, text, className) {
    const item = document.createElement(tag);
    if (text !== undefined) item.textContent = text;
    if (className) item.className = className;
    return item;
  }
  function haptic(kind="selection") {
    try {
      if (tg && tg.HapticFeedback && tg.isVersionAtLeast("6.1")) {
        if (kind==="selection") tg.HapticFeedback.selectionChanged();
        else tg.HapticFeedback.impactOccurred("light");
      }
    } catch (_) { /* Optional on older Telegram clients. */ }
  }
  function theme() {
    const values = tg ? tg.themeParams : {};
    Object.keys(values).forEach((key) => {
      if (/^#[0-9a-f]{6}$/i.test(values[key] || "")) {
        document.documentElement.style.setProperty("--tg-theme-"+key.replaceAll("_","-"),values[key]);
      }
    });
  }
  async function api(path) {
    try {
      const response = await fetch("/webapp/api/"+path, {
        headers:{"X-Telegram-Init-Data":tg.initData},cache:"no-store"});
      const data = await response.json();
      if (!response.ok) {const error=new Error(); error.publicMessage=data.error||copy.error; throw error;}
      return data;
    } catch (error) {if (!error.publicMessage) error.publicMessage=copy.error; throw error;}
  }
  function clear() {content.textContent=""; content.setAttribute("aria-busy","false"); countdown=null;}
  function skeleton() {
    clear(); content.setAttribute("aria-busy","true");
    const box=node("div",undefined,"skeletons"); box.setAttribute("aria-label",copy.loading);
    box.append(node("div",undefined,"skeleton skeleton-avatar"));
    for (let i=0;i<4;i++) box.append(node("div",undefined,"skeleton"));
    content.append(box);
  }
  function showError(text) {clear(); content.append(node("p",text,"error"));}
  function avatar(entry) {
    const circle=node("span",undefined,"avatar");
    if (/^data:image\/png;base64,/.test(entry.avatar||"")) {
      const image=node("img"); image.src=entry.avatar; image.alt=entry.name||"";
      image.width=56; image.height=56; circle.append(image);
    } else {circle.textContent=(entry.name||"?").split(/\s+/).slice(0,2).map(word=>Array.from(word)[0]||"").join("").toLocaleUpperCase();}
    return circle;
  }
  function stat(value,label) {
    const item=node("div",undefined,"stat"); item.append(node("strong",value),node("span",label)); return item;
  }
  function levelLabel(level) {return copy.level+" "+level.number+" · "+level.title;}
  function gallery(items) {
    const list=node("div",undefined,"gallery");
    items.forEach(entry=>{
      const tile=node("div",undefined,"achievement "+(entry.unlocked_at?"earned":"locked"));
      tile.append(node("span",entry.unlocked_at?"✓":"○","achievement-mark"),
                  node("strong",entry.label),node("small",entry.unlocked_at?copy.unlocked:copy.locked));
      list.append(tile);
    });
    return list;
  }
  function updateCountdown() {
    if (!countdown || !document.contains(countdown.element)) return;
    const minutes=Math.max(0,Math.ceil((Date.parse(countdown.at)-Date.now())/60000));
    if (!Number.isFinite(minutes)) return;
    countdown.element.textContent=copy.season_ends+": "+Math.floor(minutes/1440)+" "+copy.days+" "+
      Math.floor(minutes%1440/60)+" "+copy.hours+" "+minutes%60+" "+copy.minutes;
  }
  function season(at) {
    const element=node("p",undefined,"season-countdown"); content.append(element);
    countdown={at,element}; updateCountdown();
  }
  async function profile(version) {
    const data=state.profile;
    const header=node("div",undefined,"profile-heading");
    const name=node("div"); name.append(node("h2",data.name),node("p",data.username?"@"+data.username:"","muted"));
    header.append(avatar(data),name); content.append(header);
    const level=data.level;
    if (level) {
      content.append(node("p",levelLabel(level),"level-badge"));
      const progress=node("progress"); progress.max=100; progress.value=level.progress;
      progress.setAttribute("aria-label",copy.level); content.append(progress);
      content.append(node("p",level.next_threshold===null?copy.max_level:
        copy.next_level.replace("{points}",String(level.remaining)),"muted"));
    }
    const stats=node("div",undefined,"stats");
    stats.append(stat(data.points,copy.total_points),stat(data.achievements,copy.achievement_count));
    content.append(stats);
    let items=data.gallery||[], end=data.season_ends_at;
    if (state.group) {
      const response=await api("achievements?chat_id="+encodeURIComponent(state.group));
      if (version!==state.version) return;
      items=response.items; end=response.season_ends_at;
    }
    season(end); content.append(node("h3",copy.gallery),gallery(items));
  }
  async function render() {
    const version=++state.version;
    document.querySelectorAll("nav button").forEach(button=>button.setAttribute("aria-pressed",String(button.dataset.tab===state.tab)));
    clear();
    if (state.tab==="rules") {
      const chips=node("div",undefined,"game-chips");
      (copy.games||[]).forEach(name=>chips.append(node("span",name)));
      content.append(node("h2",copy.rules_title),chips,node("p",copy.rules,"rules")); return;
    }
    if (!tg || !tg.initData || !state.profile) {showError(copy.telegram_only);return;}
    try {
      if (state.tab==="profile") {await profile(version);return;}
      if (!state.group) {showError(copy.choose_group);return;}
      skeleton();
      const query="chat_id="+encodeURIComponent(state.group);
      const data=await api(state.tab==="leaderboard"?"leaderboard?"+query+"&scope="+state.scope:"achievements?"+query);
      if (version!==state.version) return;
      clear();
      const option=Array.from(byId("group").options).find(entry=>entry.value===String(data.group.id));
      if (option) option.textContent=data.group.title;
      content.append(node("h2",data.group.title));
      if (state.tab==="leaderboard") {
        const scope=node("select"); scope.setAttribute("aria-label",copy.period);
        [["season",copy.season],["all",copy.all_time]].forEach(([value,label])=>{
          const item=node("option",label); item.value=value; item.selected=value===state.scope; scope.append(item);
        });
        scope.addEventListener("change",()=>{state.scope=scope.value;haptic();render();});
        content.append(scope,node("p",data.label,"muted")); season(data.season_ends_at);
        if (!data.items.length) content.append(node("p",copy.no_scores,"muted"));
        const list=node("ol");
        data.items.forEach((entry,index)=>{
          const row=node("li",undefined,index<3?"podium podium-"+index:"");
          const name=node("div",undefined,"name"); name.append(node("strong",entry.name));
          if (entry.level) name.append(node("small",levelLabel(entry.level),"muted"));
          row.append(node("span",copy.medals[index]||String(index+1),"rank"),avatar(entry),name,
                     node("span",String(entry.points)+" "+copy.points,"score")); list.append(row);
        }); content.append(list);
      } else {content.append(gallery(data.items));season(data.season_ends_at);}
    } catch (error) {if (version===state.version) showError(error.publicMessage||copy.error);}
  }
  [["title","title"],["tagline","tagline"],["read-only","read_only"],["group-label","group"],
   ["group-hint","group_hint"],["refresh","refresh"],["privacy-note","privacy"]]
    .forEach(([id,key])=>{byId(id).textContent=copy[key];});
  [["profile",copy.profile],["leaderboard",copy.leaderboard],["achievements",copy.achievements],["rules",copy.rules_title]]
    .forEach(([tab,label])=>{
      const button=node("button",label);button.type="button";button.dataset.tab=tab;
      button.addEventListener("click",()=>{if(state.tab===tab)return;state.tab=tab;haptic();render();});byId("tabs").append(button);
    });
  byId("group").addEventListener("change",()=>{state.group=byId("group").value;haptic();render();});
  async function boot() {
    if (!tg || !tg.initData) {render();return;}
    byId("refresh").disabled=true;skeleton();
    try {
      state.profile=await api("profile");
      const start=tg.initDataUnsafe&&tg.initDataUnsafe.start_param;
      if (!state.group && /^-[0-9]{1,19}$/.test(start||"")) state.group=start;
      const groups=state.profile.groups.slice();
      if (state.group&&!groups.some(group=>String(group.id)===state.group)) groups.unshift({id:state.group,title:copy.link_group});
      byId("group").textContent="";
      groups.forEach(group=>{const option=node("option",group.title);option.value=String(group.id);byId("group").append(option);});
      if (!state.group&&groups.length) state.group=String(groups[0].id);
      byId("group").value=state.group;
      if (start&&state.tab==="profile") state.tab="leaderboard";
      await render();
    } catch (error) {showError(error.publicMessage||copy.error);}
    finally {byId("refresh").disabled=false;}
  }
  byId("refresh").addEventListener("click",()=>{haptic("impact");boot();});
  theme();if(tg){tg.ready();tg.expand();tg.onEvent("themeChanged",theme);}
  setInterval(updateCountdown,60000);boot();
})();
