<template>
  <div class="max-w-7xl mx-auto px-4 py-8">
    <!-- Header -->
    <div class="mb-8">
      <h1 class="text-3xl font-bold mb-2">엔티티 탐색</h1>
      <p class="text-gray-400">추출된 프로세스 요소들을 확인하고 출처를 추적합니다</p>
    </div>

    <!-- Stats Cards -->
    <div class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4 mb-8">
      <template v-for="(count, key) in filteredStats" :key="key">
        <div 
          class="glass rounded-xl p-4 cursor-pointer transition-all hover:scale-105"
          :class="{ 'ring-2 ring-blue-500': activeTab === key }"
          @click="activeTab = key"
        >
          <div class="text-2xl font-bold" :class="getColorClass(key)">{{ count }}</div>
          <div class="text-sm text-gray-400">{{ getLabel(key) }}</div>
        </div>
      </template>
    </div>

    <!-- Tab Navigation -->
    <div class="flex space-x-2 mb-6 overflow-x-auto pb-2">
      <button 
        v-for="tab in tabs" 
        :key="tab.key"
        @click="activeTab = tab.key"
        class="px-4 py-2 rounded-lg text-sm font-medium whitespace-nowrap transition-all"
        :class="activeTab === tab.key ? 'bg-blue-500 text-white' : 'bg-white/10 text-gray-400 hover:bg-white/20'"
      >
        {{ tab.icon }} {{ tab.label }}
      </button>
    </div>

    <!-- Content Area -->
    <div class="glass rounded-2xl overflow-hidden">
      <!-- Processes -->
      <div v-if="activeTab === 'processes'" class="divide-y divide-white/10">
        <div 
          v-for="process in processes" 
          :key="process.proc_id"
          class="p-4 hover:bg-white/5 cursor-pointer transition-all"
          @click="selectEntity('process', process)"
        >
          <div class="flex items-center justify-between">
            <div>
              <h3 class="font-medium text-lg">{{ process.name }}</h3>
              <p class="text-sm text-gray-400">{{ process.purpose || process.description }}</p>
            </div>
            <div class="flex items-center space-x-4">
              <span class="px-2 py-1 bg-blue-500/20 text-blue-400 rounded text-xs">
                {{ process.taskCount || 0 }} 태스크
              </span>
              <EvidenceBadge :evidence="process.evidence" @click.stop="showEvidence(process.evidence)" />
            </div>
          </div>
        </div>
        <div v-if="processes.length === 0" class="p-8 text-center text-gray-400">
          데이터가 없습니다. 먼저 PDF를 변환해주세요.
        </div>
      </div>

      <!-- Tasks -->
      <div v-if="activeTab === 'tasks'" class="divide-y divide-white/10">
        <div 
          v-for="task in tasks" 
          :key="task.task_id"
          class="p-4 hover:bg-white/5 cursor-pointer transition-all"
          @click="selectEntity('task', task)"
        >
          <div class="flex items-start justify-between">
            <div class="flex-1">
              <div class="flex items-center space-x-2 mb-1">
                <span class="text-xs px-2 py-0.5 rounded" :class="taskTypeClass(task.task_type)">
                  {{ task.task_type }}
                </span>
                <h3 class="font-medium">{{ task.name }}</h3>
              </div>
              <p class="text-sm text-gray-400 mb-2">{{ task.description }}</p>
              
              <!-- Flow info -->
              <div class="flex items-center space-x-4 text-xs text-gray-500">
                <span v-if="task.prev_tasks?.length">← {{ task.prev_tasks.join(', ') }}</span>
                <span v-if="task.next_tasks?.length">→ {{ task.next_tasks.join(', ') }}</span>
              </div>
            </div>
            <div class="flex items-center space-x-4 ml-4">
              <span v-if="task.role_name" class="px-2 py-1 bg-purple-500/20 text-purple-400 rounded text-xs">
                👤 {{ task.role_name }}
              </span>
              <span v-if="task.process_name" class="px-2 py-1 bg-green-500/20 text-green-400 rounded text-xs">
                📁 {{ task.process_name }}
              </span>
              <EvidenceBadge :evidence="task.evidence" @click.stop="showEvidence(task.evidence)" />
            </div>
          </div>
        </div>
      </div>

      <!-- Roles -->
      <div v-if="activeTab === 'roles'" class="divide-y divide-white/10">
        <div 
          v-for="role in roles" 
          :key="role.role_id"
          class="p-4 hover:bg-white/5 cursor-pointer transition-all"
          @click="selectEntity('role', role)"
        >
          <div class="flex items-center justify-between">
            <div>
              <h3 class="font-medium text-lg">👤 {{ role.name }}</h3>
              <p class="text-sm text-gray-400">{{ role.org_unit || role.persona_hint }}</p>
            </div>
            <div class="flex items-center space-x-4">
              <span class="px-2 py-1 bg-blue-500/20 text-blue-400 rounded text-xs">
                {{ role.taskCount || 0 }} 태스크
              </span>
              <span class="px-2 py-1 bg-orange-500/20 text-orange-400 rounded text-xs">
                {{ role.decisionCount || 0 }} 결정
              </span>
              <EvidenceBadge :evidence="role.evidence" @click.stop="showEvidence(role.evidence)" />
            </div>
          </div>
        </div>
      </div>

      <!-- Decisions -->
      <div v-if="activeTab === 'decisions'" class="divide-y divide-white/10">
        <div 
          v-for="decision in decisions" 
          :key="decision.decision_id"
          class="p-4 hover:bg-white/5 cursor-pointer transition-all"
          @click="selectEntity('decision', decision)"
        >
          <div class="flex items-center justify-between">
            <div>
              <h3 class="font-medium text-lg">📊 {{ decision.name }}</h3>
              <p class="text-sm text-gray-400">{{ decision.description }}</p>
              <div v-if="decision.roles?.length" class="mt-2 flex items-center space-x-2">
                <span class="text-xs text-gray-500">담당:</span>
                <span 
                  v-for="role in decision.roles" 
                  :key="role"
                  class="px-2 py-0.5 bg-purple-500/20 text-purple-400 rounded text-xs"
                >
                  {{ role }}
                </span>
              </div>
            </div>
            <div class="flex items-center space-x-4">
              <span class="px-2 py-1 bg-yellow-500/20 text-yellow-400 rounded text-xs">
                {{ decision.ruleCount || 0 }} 규칙
              </span>
              <EvidenceBadge :evidence="decision.evidence" @click.stop="showEvidence(decision.evidence)" />
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Evidence Modal -->
    <div 
      v-if="evidenceModal" 
      class="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50"
      @click.self="evidenceModal = null"
    >
      <div class="glass rounded-2xl p-6 max-w-2xl w-full mx-4 max-h-[80vh] overflow-y-auto">
        <div class="flex items-center justify-between mb-4">
          <h3 class="text-xl font-bold">📄 출처 정보</h3>
          <button @click="evidenceModal = null" class="text-gray-400 hover:text-white">
            <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
        
        <div class="space-y-4">
          <div class="flex items-center space-x-4 p-3 bg-white/5 rounded-lg">
            <div class="w-10 h-10 rounded-lg bg-red-500/20 flex items-center justify-center">
              <svg class="w-5 h-5 text-red-400" fill="currentColor" viewBox="0 0 24 24">
                <path d="M14,2H6A2,2 0 0,0 4,4V20A2,2 0 0,0 6,22H18A2,2 0 0,0 20,20V8L14,2M18,20H6V4H13V9H18V20Z"/>
              </svg>
            </div>
            <div>
              <div class="font-medium">페이지 {{ evidenceModal.page }}</div>
              <div class="text-sm text-gray-400">process_sample1.pdf</div>
            </div>
          </div>
          
          <div>
            <label class="text-sm text-gray-400 block mb-2">추출된 텍스트</label>
            <div class="p-4 bg-slate-800 rounded-lg text-sm leading-relaxed font-mono">
              {{ evidenceModal.text }}
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useAppStore } from '../stores/app'

// Evidence Badge Component (inline)
const EvidenceBadge = {
  props: ['evidence'],
  template: `
    <button 
      v-if="evidence?.page" 
      class="px-2 py-1 bg-emerald-500/20 text-emerald-400 rounded text-xs hover:bg-emerald-500/30 transition-all"
    >
      📄 p.{{ evidence.page }}
    </button>
  `
}

const store = useAppStore()
const route = useRoute()

const activeTab = ref('processes')
const evidenceModal = ref(null)
const selectedEntity = ref(null)

const tabs = [
  { key: 'processes', label: '프로세스', icon: '🔄' },
  { key: 'tasks', label: '태스크', icon: '📋' },
  { key: 'roles', label: '역할', icon: '👤' },
  { key: 'decisions', label: 'DMN 결정', icon: '📊' },
]

const stats = computed(() => store.stats || {})
const filteredStats = computed(() => {
  const result = {}
  for (const [key, value] of Object.entries(stats.value)) {
    if (typeof key === 'string' && !key.startsWith('relationships')) {
      result[key] = value
    }
  }
  return result
})
const processes = computed(() => store.processes)
const tasks = computed(() => store.tasks)
const roles = computed(() => store.roles)
const decisions = computed(() => store.decisions)

function getColorClass(key) {
  const colors = {
    processes: 'text-blue-400',
    tasks: 'text-purple-400',
    roles: 'text-green-400',
    gateways: 'text-yellow-400',
    decisions: 'text-orange-400',
    documents: 'text-red-400',
  }
  return colors[key] || 'text-gray-400'
}

function getLabel(key) {
  const labels = {
    processes: '프로세스',
    tasks: '태스크',
    roles: '역할',
    gateways: '게이트웨이',
    events: '이벤트',
    decisions: 'DMN 결정',
    rules: 'DMN 규칙',
    skills: '스킬',
    documents: '문서',
    chunks: '청크',
  }
  return labels[key] || key
}

function taskTypeClass(type) {
  return {
    'bg-blue-500/20 text-blue-400': type === 'human',
    'bg-purple-500/20 text-purple-400': type === 'agent',
    'bg-green-500/20 text-green-400': type === 'system',
  }
}

function selectEntity(type, entity) {
  selectedEntity.value = { type, ...entity }
}

function showEvidence(evidence) {
  if (evidence?.page) {
    evidenceModal.value = evidence
  }
}

onMounted(async () => {
  await Promise.all([
    store.fetchStats(),
    store.fetchProcesses(),
    store.fetchTasks(),
    store.fetchRoles(),
    store.fetchDecisions(),
  ])
  
  // Set tab from route
  if (route.params.type) {
    activeTab.value = route.params.type
  }
})

watch(() => route.params.type, (type) => {
  if (type) activeTab.value = type
})
</script>

