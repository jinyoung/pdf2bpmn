import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'
import './assets/main.css'

// Routes
import HomeView from './views/HomeView.vue'
import ProcessView from './views/ProcessView.vue'
import EntitiesView from './views/EntitiesView.vue'

const routes = [
  { path: '/', name: 'home', component: HomeView },
  { path: '/process', name: 'process', component: ProcessView },
  { path: '/entities', name: 'entities', component: EntitiesView },
  { path: '/entities/:type', name: 'entity-type', component: EntitiesView },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.mount('#app')




