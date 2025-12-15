<template>
  <div class="max-w-4xl mx-auto px-4 py-12">
    <!-- Header -->
    <div class="text-center mb-12 animate-fade-in">
      <h1 class="text-4xl font-bold mb-4">
        <span class="bg-gradient-to-r from-blue-400 via-purple-400 to-pink-400 bg-clip-text text-transparent">
          PDF to BPMN Converter
        </span>
      </h1>
      <p class="text-gray-400 text-lg">
        업무 편람/정의서를 BPMN, DMN, Agent Skill 문서로 자동 변환
      </p>
    </div>

    <!-- Upload Area -->
    <div 
      v-if="!currentJob || currentJob.status === 'error'"
      class="glass rounded-2xl p-8 mb-8 animate-slide-up"
      :class="{ 'border-2 border-blue-500 glow-effect': isDragging }"
      @dragover.prevent="isDragging = true"
      @dragleave="isDragging = false"
      @drop.prevent="handleDrop"
    >
      <div class="text-center">
        <div class="w-20 h-20 mx-auto mb-6 rounded-full bg-gradient-to-br from-blue-500/20 to-purple-500/20 flex items-center justify-center">
          <svg class="w-10 h-10 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
          </svg>
        </div>
        
        <h3 class="text-xl font-semibold mb-2">PDF 파일 업로드</h3>
        <p class="text-gray-400 mb-6">파일을 드래그하거나 클릭하여 선택하세요</p>
        
        <input 
          type="file" 
          ref="fileInput" 
          @change="handleFileSelect" 
          accept=".pdf"
          class="hidden"
        />
        
        <button 
          @click="$refs.fileInput.click()"
          class="px-6 py-3 bg-gradient-to-r from-blue-500 to-purple-600 rounded-lg font-medium hover:from-blue-600 hover:to-purple-700 transition-all transform hover:scale-105"
        >
          파일 선택
        </button>
      </div>
    </div>

    <!-- Error Message -->
    <div v-if="store.error" class="glass rounded-xl p-4 mb-8 border border-red-500/50 bg-red-500/10">
      <div class="flex items-center space-x-3">
        <svg class="w-6 h-6 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        <span class="text-red-300">{{ store.error }}</span>
      </div>
    </div>

    <!-- Processing Status -->
    <div v-if="currentJob && currentJob.status !== 'error'" class="glass rounded-2xl p-8 animate-slide-up">
      <!-- File Info -->
      <div class="flex items-center justify-between mb-6 pb-6 border-b border-white/10">
        <div class="flex items-center space-x-4">
          <div class="w-12 h-12 rounded-lg bg-red-500/20 flex items-center justify-center">
            <svg class="w-6 h-6 text-red-400" fill="currentColor" viewBox="0 0 24 24">
              <path d="M14,2H6A2,2 0 0,0 4,4V20A2,2 0 0,0 6,22H18A2,2 0 0,0 20,20V8L14,2M18,20H6V4H13V9H18V20Z"/>
            </svg>
          </div>
          <div>
            <h4 class="font-medium">{{ currentJob.file_name }}</h4>
            <p class="text-sm text-gray-400">업로드됨</p>
          </div>
        </div>
        <span 
          class="px-3 py-1 rounded-full text-sm font-medium"
          :class="statusClass"
        >
          {{ statusText }}
        </span>
      </div>

      <!-- Progress Bar -->
      <div class="mb-8">
        <div class="flex items-center justify-between mb-2">
          <span class="text-sm text-gray-400">전체 진행률</span>
          <span class="text-sm font-mono text-blue-400">{{ currentJob.progress }}%</span>
        </div>
        <div class="h-2 bg-gray-700 rounded-full overflow-hidden">
          <div 
            class="h-full progress-bar rounded-full transition-all duration-300"
            :style="{ width: currentJob.progress + '%' }"
          ></div>
        </div>
      </div>

      <!-- Step List -->
      <div class="space-y-3">
        <div 
          v-for="(step, index) in currentJob.steps" 
          :key="step.name"
          class="flex items-center space-x-4 p-3 rounded-lg transition-all"
          :class="stepClass(step)"
        >
          <!-- Step Icon -->
          <div class="w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0"
               :class="stepIconClass(step)">
            <svg v-if="step.status === 'completed'" class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
              <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd"/>
            </svg>
            <svg v-else-if="step.status === 'processing'" class="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            <span v-else class="text-xs font-mono">{{ index + 1 }}</span>
          </div>
          
          <!-- Step Info -->
          <div class="flex-1">
            <span class="font-medium">{{ step.label }}</span>
          </div>
          
          <!-- Status Badge -->
          <span 
            v-if="step.status === 'processing'"
            class="text-xs text-blue-400 animate-pulse"
          >
            처리 중...
          </span>
        </div>
      </div>

      <!-- Start Button -->
      <div v-if="currentJob.status === 'pending'" class="mt-8 text-center">
        <button 
          @click="startProcessing"
          class="px-8 py-3 bg-gradient-to-r from-green-500 to-emerald-600 rounded-lg font-medium hover:from-green-600 hover:to-emerald-700 transition-all transform hover:scale-105"
        >
          🚀 변환 시작
        </button>
      </div>

      <!-- Completion Actions -->
      <div v-if="currentJob.status === 'completed'" class="mt-8 pt-6 border-t border-white/10">
        <div class="grid grid-cols-3 gap-4 mb-6">
          <div class="text-center p-4 rounded-lg bg-white/5">
            <div class="text-2xl font-bold text-blue-400">{{ currentJob.result?.processes || 0 }}</div>
            <div class="text-sm text-gray-400">프로세스</div>
          </div>
          <div class="text-center p-4 rounded-lg bg-white/5">
            <div class="text-2xl font-bold text-purple-400">{{ currentJob.result?.tasks || 0 }}</div>
            <div class="text-sm text-gray-400">태스크</div>
          </div>
          <div class="text-center p-4 rounded-lg bg-white/5">
            <div class="text-2xl font-bold text-green-400">{{ currentJob.result?.roles || 0 }}</div>
            <div class="text-sm text-gray-400">역할</div>
          </div>
        </div>
        
        <div class="flex items-center justify-center space-x-4">
          <router-link 
            to="/process"
            class="px-6 py-3 bg-gradient-to-r from-blue-500 to-purple-600 rounded-lg font-medium hover:from-blue-600 hover:to-purple-700 transition-all"
          >
            📊 프로세스 보기
          </router-link>
          <router-link 
            to="/entities"
            class="px-6 py-3 bg-white/10 rounded-lg font-medium hover:bg-white/20 transition-all"
          >
            🔍 엔티티 탐색
          </router-link>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useAppStore } from '../stores/app'

const store = useAppStore()
const fileInput = ref(null)
const isDragging = ref(false)

const currentJob = computed(() => store.currentJob)

const statusClass = computed(() => {
  const status = currentJob.value?.status
  return {
    'bg-yellow-500/20 text-yellow-400': status === 'pending',
    'bg-blue-500/20 text-blue-400': status === 'processing',
    'bg-green-500/20 text-green-400': status === 'completed',
    'bg-red-500/20 text-red-400': status === 'error',
  }
})

const statusText = computed(() => {
  const status = currentJob.value?.status
  return {
    'pending': '대기 중',
    'processing': '처리 중',
    'completed': '완료',
    'error': '오류'
  }[status] || status
})

function stepClass(step) {
  return {
    'bg-white/5': step.status === 'pending',
    'bg-blue-500/10 border border-blue-500/30': step.status === 'processing',
    'bg-green-500/10': step.status === 'completed',
  }
}

function stepIconClass(step) {
  return {
    'bg-gray-600 text-gray-400': step.status === 'pending',
    'bg-blue-500 text-white': step.status === 'processing',
    'bg-green-500 text-white': step.status === 'completed',
  }
}

async function handleFileSelect(event) {
  const file = event.target.files[0]
  if (file) {
    await uploadAndProcess(file)
  }
}

async function handleDrop(event) {
  isDragging.value = false
  const file = event.dataTransfer.files[0]
  if (file && file.name.endsWith('.pdf')) {
    await uploadAndProcess(file)
  }
}

async function uploadAndProcess(file) {
  try {
    await store.uploadFile(file)
  } catch (e) {
    console.error('Upload failed:', e)
  }
}

async function startProcessing() {
  const jobId = currentJob.value?.job_id
  if (!jobId) return
  
  const started = await store.startProcessing(jobId)
  if (started) {
    store.subscribeToJob(jobId, (data) => {
      // Job updated via SSE
    })
  }
}
</script>




