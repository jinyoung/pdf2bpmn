<template>
  <div class="min-h-screen flex flex-col">
    <!-- Navigation -->
    <nav class="glass sticky top-0 z-50 border-b border-white/10">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div class="flex items-center justify-between h-16">
          <div class="flex items-center">
            <router-link to="/" class="flex items-center space-x-3">
              <div class="w-10 h-10 rounded-lg bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center">
                <svg class="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
              </div>
              <span class="text-xl font-bold bg-gradient-to-r from-blue-400 to-purple-400 bg-clip-text text-transparent">
                PDF2BPMN
              </span>
            </router-link>
          </div>
          
          <div class="flex items-center space-x-4">
            <router-link 
              to="/" 
              class="px-4 py-2 rounded-lg text-sm font-medium transition-all"
              :class="$route.path === '/' ? 'bg-white/10 text-white' : 'text-gray-400 hover:text-white hover:bg-white/5'"
            >
              업로드
            </router-link>
            <router-link 
              to="/process" 
              class="px-4 py-2 rounded-lg text-sm font-medium transition-all"
              :class="$route.path === '/process' ? 'bg-white/10 text-white' : 'text-gray-400 hover:text-white hover:bg-white/5'"
            >
              프로세스 뷰어
            </router-link>
            <router-link 
              to="/entities" 
              class="px-4 py-2 rounded-lg text-sm font-medium transition-all"
              :class="$route.path.startsWith('/entities') ? 'bg-white/10 text-white' : 'text-gray-400 hover:text-white hover:bg-white/5'"
            >
              엔티티 탐색
            </router-link>
          </div>
        </div>
      </div>
    </nav>

    <!-- Main Content -->
    <main class="flex-1">
      <router-view />
    </main>

    <!-- Footer -->
    <footer class="glass border-t border-white/10 py-4">
      <div class="max-w-7xl mx-auto px-4 text-center text-sm text-gray-500">
        PDF2BPMN Converter • Powered by LangGraph & Neo4j
      </div>
    </footer>
  </div>
</template>

<script setup>
</script>




