<template>
  <div>
    <h1 class="brand">成员</h1>
    <form @submit.prevent="add">
      <input v-model="name" placeholder="新成员姓名" />
      <button type="submit">添加</button>
    </form>
    <ul class="list">
      <li v-for="m in rows" :key="m.id">
        <strong>{{ m.name }}</strong>
        <span class="muted"> · {{ m.active ? '在岗' : '停用' }} · {{ m.data_quality }}</span>
        <div class="memorial-row">
          <span class="muted">现行忌日：</span>
          <button
            v-for="d in days7"
            :key="d"
            type="button"
            class="day-toggle"
            :class="{ on: isPicked(m, d) }"
            @click="toggle(m, d)"
          >D{{ d }}</button>
          <button type="button" @click="save(m)">保存忌日</button>
          <span v-if="savedId === m.id" class="ok">已存</span>
        </div>
        <div v-if="pinnedDays(m.id).length" class="muted pinned">
          回看第 {{ selectedWeek }} 周忌日（快照同钉）：
          <span v-for="d in pinnedDays(m.id)" :key="d" class="chip memorial">D{{ d }}</span>
        </div>
      </li>
    </ul>

    <section class="week-card" style="margin-top:12px">
      <header>回看已生成周</header>
      <p class="muted">只改现行忌日不会回刷已生成周；此处显示生成当周钉住的忌日集合。</p>
      <select v-model="selectedWeek" @change="loadSnapshot">
        <option v-for="w in weeks" :key="w.id" :value="w.id">{{ w.label }}（#{{ w.id }} · {{ w.status }}）</option>
      </select>
      <p v-if="!hasPinned" class="muted">该周无忌日快照或尚未生成。</p>
    </section>
  </div>
</template>
<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../api'
const rows = ref([])
const weeks = ref([])
const name = ref('')
const days7 = [0,1,2,3,4,5,6]
const draft = ref({})           // memberId -> [days] 现行忌日草稿
const selectedWeek = ref(1)
const snapshot = ref({})        // 回看周的钉住快照 { "memberId": [days] }
const savedId = ref(0)
let errTimer
function isPicked(m, d) { return (draft.value[m.id] || []).includes(d) }
function toggle(m, d) {
  const cur = draft.value[m.id] ? [...draft.value[m.id]] : []
  const i = cur.indexOf(d)
  if (i >= 0) cur.splice(i, 1); else cur.push(d)
  cur.sort((a, b) => a - b)
  draft.value[m.id] = cur
}
async function save(m) {
  await api('/members/' + m.id + '/memorial', {
    method: 'PUT', body: JSON.stringify({ days: draft.value[m.id] || [] }),
  })
  m.memorial_days = [...(draft.value[m.id] || [])]
  savedId.value = m.id
  clearTimeout(errTimer)
  errTimer = setTimeout(() => (savedId.value = 0), 1500)
}
function pinnedDays(mid) { return snapshot.value[String(mid)] || [] }
const hasPinned = ref(false)
async function load() {
  rows.value = await api('/members')
  for (const m of rows.value) draft.value[m.id] = [...(m.memorial_days || [])]
  weeks.value = await api('/weeks')
  if (weeks.value.length && !weeks.value.find(w => w.id === selectedWeek.value)) {
    selectedWeek.value = weeks.value[0].id
  }
  await loadSnapshot()
}
async function loadSnapshot() {
  try {
    const b = await api('/weeks/' + selectedWeek.value + '/board')
    snapshot.value = b.memorial_snapshot || {}
  } catch { snapshot.value = {} }
  hasPinned.value = Object.keys(snapshot.value).length > 0
}
async function add() {
  if (!name.value.trim()) return
  await api('/members', { method: 'POST', body: JSON.stringify({ name: name.value }) })
  name.value = ''; await load()
}
onMounted(load)
</script>
