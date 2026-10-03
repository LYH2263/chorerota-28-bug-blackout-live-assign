<template>
  <div>
    <h1 class="brand">本周看板</h1>
    <p class="muted">周卡片网格 · round-robin 落位后可去「对调」申请交换 · 忌日成员自动跳格、相位前进</p>
    <div style="display:flex;gap:8px;margin:12px 0">
      <button @click="generate">生成周表</button>
      <button class="ghost" @click="load">刷新</button>
    </div>
    <section v-if="memorialRows.length" class="week-card memorial-banner">
      <header>本周忌日快照（生成时钉住，改现行忌日不回刷）</header>
      <span v-for="r in memorialRows" :key="r.id" class="chip memorial">
        {{ r.name }}：D{{ r.days.join('、D') }}
      </span>
    </section>
    <p v-if="err" class="err">{{ err }}</p>
    <div class="week-grid">
      <article v-for="d in days" :key="d" class="week-card">
        <header>
          Day {{ d }}
          <span v-if="memorialNames(d).length" class="memorial-mark">忌 {{ memorialNames(d).join('、') }}</span>
        </header>
        <div v-for="a in byDay(d)" :key="a.id">
          <span class="chip">{{ a.task_title }}</span>
          <span class="chip coral">{{ a.member_name }}</span>
        </div>
        <p v-if="!byDay(d).length" class="muted">空</p>
      </article>
    </div>
  </div>
</template>
<script setup>
import { ref, computed, onMounted } from 'vue'
import { api } from '../api'
const assigns = ref([])
const snapshot = ref({})
const memberNames = ref({})
const days = [0,1,2,3,4,5,6]
const err = ref('')
const weekId = 1
function byDay(d) { return assigns.value.filter(a => a.day === d) }
const memorialRows = computed(() =>
  Object.entries(snapshot.value)
    .map(([mid, ds]) => ({ id: mid, name: memberNames.value[mid] || ('#' + mid), days: ds }))
    .filter(r => r.days.length)
)
function memorialNames(day) {
  return memorialRows.value.filter(r => r.days.includes(day)).map(r => r.name)
}
async function load() {
  err.value = ''
  try {
    const b = await api('/weeks/' + weekId + '/board')
    assigns.value = b.assignments || []
    snapshot.value = b.memorial_snapshot || {}
    const names = {}
    for (const a of assigns.value) names[a.member_id] = a.member_name
    try {
      for (const m of await api('/members')) names[m.id] = m.name
    } catch {}
    memberNames.value = names
  } catch (e) { err.value = e.message }
}
async function generate() {
  err.value = ''
  try {
    await api('/weeks/' + weekId + '/generate', { method: 'POST', body: '{}' })
    await load()
  } catch (e) {
    // 全员忌日等失败：服务端保持原格，重新拉取确认看板与回包一致
    err.value = friendlyError(e.message)
    await load()
  }
}
function friendlyError(code) {
  if (code === 'all_unavailable') return '当天全员忌日，生成失败，周表保持原样。'
  return code
}
onMounted(load)
</script>
