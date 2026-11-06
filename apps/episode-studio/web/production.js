/* Read completed native nodes; generation remains owned by the runtime. */
class ProductionPreview {
  constructor(api, token, say) {
    Object.assign(this, {api, token, say, generation: 0, pending: new Set(), loaded: new Set(), urls: []});
  }
  reset() {
    this.generation++;
    this.pending.clear(); this.loaded.clear(); this.selected = new Map(); this.planned = 0;
    this.urls.forEach(url => URL.revokeObjectURL(url)); this.urls = [];
    for (const id of ['storyboard', 'cast-assets', 'shot-assets']) document.getElementById(id).replaceChildren();
    document.getElementById('production-assets').hidden = true;
  }
  async media(asset, generation) {
    const name = new URL(asset.uri, location.href).pathname.split('/').at(-1);
    if (!/^[a-f0-9]{32,64}(?:_[0-9]+)?\.(mp4|wav|png|jpg)$/.test(name)) throw Error('Invalid media asset');
    const path = '/episode-media/' + name;
    if (!this.token()) return path;
    const response = await fetch(path, {headers: {Authorization: 'Bearer ' + this.token()}});
    if (!response.ok) throw Error('Could not load the preview');
    const blob = await response.blob();
    if (generation !== this.generation) return null;
    const url = URL.createObjectURL(blob); this.urls.push(url); return url;
  }
  async update(run, events, plan) {
    if (plan && !this.loaded.has('graph/script_editor')) {
      await this.add('graph/script_editor', plan, this.generation);
      this.loaded.add('graph/script_editor');
      document.getElementById('production-assets').hidden = false;
    }
    for (const event of events) {
      const path = event.node_id || '';
      if (event.type === 'node.completed' && (/\/(script_editor|selected_take|first_frame)$/.test(path)
        || /\/reference_library\/item-\d+\/(generate|selected_reference)$/.test(path)
        || /\/voice_library\/item-\d+\/record$/.test(path))) this.pending.add(path);
    }
    const generation = this.generation;
    for (const path of [...this.pending]) {
      if (generation !== this.generation) return;
      if (this.loaded.has(path)) { this.pending.delete(path); continue; }
      try {
        const node = await this.api('/runs/' + run + '/nodes/' + path);
        if (generation !== this.generation) return;
        if (node.status !== 'succeeded' || !node.output) continue;
        await this.add(path, node.output, generation);
        if (generation !== this.generation) return;
        this.loaded.add(path); this.pending.delete(path);
        document.getElementById('production-assets').hidden = false;
      } catch (error) {
        // Retry this preview on the next poll without changing production state.
        if (generation === this.generation) document.getElementById('preview-state').textContent =
          this.say('Preview reconnecting…', '正在重新连接预览……');
      }
    }
    if (!this.pending.size) { const count=this.selected?.size||0, seconds=[...(this.selected?.values()||[])].reduce((a,b)=>a+b,0); document.getElementById('preview-state').textContent = this.planned ? this.say(`${count} / ${this.planned} shots selected · ${seconds.toFixed(1)}s`, `已选用 ${count} / ${this.planned} 个镜头 · ${seconds.toFixed(1)} 秒`) : ''; }
  }
  async add(path, output, generation) {
    const element = (tag, text) => { const node = document.createElement(tag); if (text) node.textContent = text; return node; };
    if (path.endsWith('/script_editor')) {
      this.planned = (output.shots || []).length;
      const panel = document.getElementById('storyboard');
      const details = element('details'), summary = element('summary', output.title), list = element('ol');
      for (const shot of output.shots || []) {
        const row = element('li'); row.append(element('strong', `${shot.id} · ${shot.duration_seconds}s`), element('p', shot.action)); list.append(row);
      }
      details.append(summary, element('p', output.logline), list); panel.replaceChildren(details); return;
    }
    const shot = /\/shots\/item-(\d+)\//.exec(path);
    const take = path.endsWith('/selected_take');
    if(take) { this.selected ||= new Map(); this.selected.set(shot[1],output.duration_seconds || output.shot.duration_seconds || 0); }
    const asset = take ? output.clip : output;
    if (!asset?.uri) return;
    const card = element('figure');
    const caption = take ? `${Number(shot[1]) + 1} · ${output.shot.action}` : shot
      ? this.say('Shot ', '镜头 ') + (Number(shot[1]) + 1) : this.say('Reference ', '参考 ') + ((Number(/item-(\d+)/.exec(path)?.[1]) || 0) + 1);
    const tag = asset.media_type.startsWith('video/') ? 'video' : asset.media_type.startsWith('audio/') ? 'audio' : 'img';
    const media = element(tag);
    if (tag === 'img') { media.alt = caption; media.loading = 'lazy'; }
    else { media.controls = true; media.preload = 'none'; if (tag === 'video') media.playsInline = true; }
    if (take && output.frame) media.poster = await this.media(output.frame, generation) || '';
    // Authenticated video/audio loads on demand, avoiding a whole-film fetch on every preview.
    if (this.token() && tag !== 'img') {
      const button = element('button', this.say('Load preview', '载入预览'));
      button.onclick = async () => { button.disabled = true; try {
        const url = await this.media(asset, generation); if (!url || generation !== this.generation) return;
        media.src = url; button.remove();
      } catch { button.disabled = false; button.textContent = this.say('Retry preview', '重试预览'); } };
      card.append(button);
    } else media.src = await this.media(asset, generation) || '';
    if (generation !== this.generation) return;
    card.append(media, element('figcaption', caption));
    if (shot) {
      const previous = document.getElementById('shot-preview-' + shot[1]);
      card.id = 'shot-preview-' + shot[1];
      if (previous) previous.replaceWith(card); else document.getElementById('shot-assets').append(card);
    } else document.getElementById('cast-assets').append(card);
  }
}
