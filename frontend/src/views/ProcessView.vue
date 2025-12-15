<template>
  <div class="h-[calc(100vh-8rem)] flex flex-col">
    <!-- Header -->
    <div class="glass border-b border-white/10 px-6 py-4">
      <div class="flex items-center justify-between">
        <div>
          <h1 class="text-2xl font-bold">프로세스 뷰어</h1>
          <p class="text-gray-400 text-sm">BPMN.io로 시각화된 프로세스 다이어그램</p>
        </div>
        <div class="flex items-center space-x-3">
          <button 
            @click="zoomIn"
            class="p-2 rounded-lg bg-white/10 hover:bg-white/20 transition-all"
            title="확대"
          >
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0zM10 7v3m0 0v3m0-3h3m-3 0H7" />
            </svg>
          </button>
          <button 
            @click="zoomOut"
            class="p-2 rounded-lg bg-white/10 hover:bg-white/20 transition-all"
            title="축소"
          >
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0zM13 10H7" />
            </svg>
          </button>
          <button 
            @click="fitToViewport"
            class="p-2 rounded-lg bg-white/10 hover:bg-white/20 transition-all"
            title="화면에 맞추기"
          >
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4" />
            </svg>
          </button>
          <a 
            href="/api/files/bpmn"
            download="process.bpmn"
            class="px-4 py-2 bg-gradient-to-r from-blue-500 to-purple-600 rounded-lg text-sm font-medium hover:from-blue-600 hover:to-purple-700 transition-all"
          >
            📥 BPMN 다운로드
          </a>
        </div>
      </div>
    </div>

    <!-- BPMN Viewer -->
    <div class="flex-1 flex">
      <!-- Diagram Area -->
      <div class="flex-1 relative bg-slate-900/50">
        <div v-if="loading" class="absolute inset-0 flex items-center justify-center">
          <div class="text-center">
            <svg class="w-12 h-12 animate-spin text-blue-500 mx-auto mb-4" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            <p class="text-gray-400">BPMN 다이어그램 로딩 중...</p>
          </div>
        </div>
        
        <div v-if="error" class="absolute inset-0 flex items-center justify-center">
          <div class="text-center">
            <svg class="w-12 h-12 text-red-500 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
            <p class="text-gray-400">{{ error }}</p>
            <button @click="loadBpmn" class="mt-4 px-4 py-2 bg-blue-500 rounded-lg">다시 시도</button>
          </div>
        </div>
        
        <div ref="bpmnContainer" class="w-full h-full"></div>
      </div>

      <!-- Side Panel: Selected Element Info -->
      <div v-if="selectedElement" class="w-80 glass border-l border-white/10 overflow-y-auto">
        <div class="p-4">
          <div class="flex items-center justify-between mb-4">
            <h3 class="font-semibold">선택된 요소</h3>
            <button @click="selectedElement = null" class="text-gray-400 hover:text-white">
              <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
          
          <div class="space-y-4">
            <div>
              <label class="text-xs text-gray-400 uppercase tracking-wider">이름</label>
              <p class="font-medium">{{ selectedElement.name || selectedElement.id }}</p>
            </div>
            
            <div>
              <label class="text-xs text-gray-400 uppercase tracking-wider">유형</label>
              <p class="text-sm">{{ selectedElement.type }}</p>
            </div>
            
            <div v-if="selectedElement.description">
              <label class="text-xs text-gray-400 uppercase tracking-wider">설명</label>
              <p class="text-sm text-gray-300">{{ selectedElement.description }}</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useAppStore } from '../stores/app'

const store = useAppStore()
const bpmnContainer = ref(null)
const loading = ref(true)
const error = ref(null)
const selectedElement = ref(null)

let bpmnViewer = null

onMounted(async () => {
  await loadBpmn()
})

onUnmounted(() => {
  if (bpmnViewer) {
    bpmnViewer.destroy()
  }
})

async function loadBpmn() {
  loading.value = true
  error.value = null
  
  try {
    const content = await store.fetchBpmnContent()
    
    if (!content) {
      error.value = 'BPMN 파일을 찾을 수 없습니다. 먼저 PDF를 변환해주세요.'
      loading.value = false
      return
    }
    
    // Dynamically import bpmn-js
    const { default: BpmnViewer } = await import('bpmn-js/lib/NavigatedViewer')
    
    if (bpmnViewer) {
      bpmnViewer.destroy()
    }
    
    bpmnViewer = new BpmnViewer({
      container: bpmnContainer.value,
      keyboard: { bindTo: document }
    })
    
    // Apply dark theme styling
    const canvas = bpmnViewer.get('canvas')
    
    await bpmnViewer.importXML(content)
    
    // Fit to viewport
    canvas.zoom('fit-viewport')
    
    // Add element selection handler
    const eventBus = bpmnViewer.get('eventBus')
    eventBus.on('element.click', (e) => {
      const element = e.element
      if (element.type !== 'bpmn:Process' && element.type !== 'label') {
        selectedElement.value = {
          id: element.id,
          name: element.businessObject?.name || element.id,
          type: element.type.replace('bpmn:', ''),
          description: element.businessObject?.documentation?.[0]?.text
        }
      }
    })
    
    loading.value = false
    
  } catch (e) {
    console.error('Failed to load BPMN:', e)
    error.value = 'BPMN 로딩 실패: ' + e.message
    loading.value = false
  }
}

function zoomIn() {
  if (bpmnViewer) {
    const canvas = bpmnViewer.get('canvas')
    canvas.zoom(canvas.zoom() * 1.2)
  }
}

function zoomOut() {
  if (bpmnViewer) {
    const canvas = bpmnViewer.get('canvas')
    canvas.zoom(canvas.zoom() * 0.8)
  }
}

function fitToViewport() {
  if (bpmnViewer) {
    const canvas = bpmnViewer.get('canvas')
    canvas.zoom('fit-viewport')
  }
}
</script>

<style>
.bjs-powered-by {
  display: none !important;
}

.djs-element .djs-visual > :first-child {
  fill: #1e293b !important;
  stroke: #64748b !important;
}

.djs-element .djs-visual text {
  fill: #e2e8f0 !important;
}

.djs-connection .djs-visual > :first-child {
  stroke: #64748b !important;
}

.djs-element:hover .djs-visual > :first-child {
  stroke: #38bdf8 !important;
}

.djs-element.selected .djs-visual > :first-child {
  stroke: #a78bfa !important;
  stroke-width: 2px !important;
}
</style>




