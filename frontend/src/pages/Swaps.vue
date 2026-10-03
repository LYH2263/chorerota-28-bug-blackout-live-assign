<template>
  <div>
    <h1 class="brand">对调</h1>
    <p class="muted">先生成周表，再填写两格对调（day + task_id）</p>
    <div class="week-card" style="margin-bottom:12px">
      <label>A day <input type="number" v-model.number="form.a_day" /></label>
      <label>A task_id <input type="number" v-model.number="form.a_task" /></label>
      <label>B day <input type="number" v-model.number="form.b_day" /></label>
      <label>B task_id <input type="number" v-model.number="form.b_task" /></label>
      <button @click="request">申请对调</button>
    </div>
    <p v-if="err" class="err">{{ err }}</p>
    <ul class="list">
      <li v-for="s in rows" :key="s.id">
        #{{ s.id }} D{{ s.a_day }}/T{{ s.a_task }} ↔ D{{ s.b_day }}/T{{ s.b_task }}
        <span class="chip" :class="{ coral: s.status==='pending' }">{{ s.status }}</span>
        <button v-if="s.status==='pending'" style="margin-left:8px" @click="confirm(s.id)">确认改表</button>
      </li>
    </ul>
  </div>
</template>
<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../api'
const rows = ref([])
const err = ref('')
const form = ref({ a_day: 0, a_task: 1, b_day: 1, b_task: 1 })
function friendlyError(code) {
  if (code === 'memorial_blocked') return '命中忌日，对调被拒。'
  if (code === 'same_assignee') return '两格本就是同一人，无需对调。'
  if (code === 'slot_missing') return '格位不存在。'
  return code
}
async function load() { rows.value = await api('/swaps') }
async function request() {
  err.value = ''
  try {
    await api('/weeks/1/swaps', { method: 'POST', body: JSON.stringify(form.value) })
    await load()
  } catch (e) { err.value = friendlyError(e.message) }
}
async function confirm(id) {
  err.value = ''
  try { await api('/swaps/' + id + '/confirm', { method: 'POST', body: '{}' }); await load() }
  catch (e) { err.value = friendlyError(e.message) }
}
onMounted(load)
</script>
