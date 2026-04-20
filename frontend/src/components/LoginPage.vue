<template>
  <div class="login-card">
    <h2>系统登录</h2>

    <div class="form-item">
      <label>用户名：</label>
      <input v-model="username" />
    </div>

    <div class="form-item">
      <label>密码：</label>
      <input v-model="password" type="password" />
    </div>

    <button @click="handleLogin">登录</button>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import axios from 'axios'

const emit = defineEmits(['login-success'])

const username = ref('admin')
const password = ref('123456')

const handleLogin = async () => {
  try {
    const res = await axios.post('http://127.0.0.1:8080/api/login', {
      username: username.value,
      password: password.value
    })

    const userInfo = res.data.data
    localStorage.setItem('userInfo', JSON.stringify(userInfo))
    emit('login-success', userInfo)
  } catch (err) {
    console.error('登录失败', err)
    alert('用户名或密码错误')
  }
}
</script>

<style scoped>
.login-card {
  width: 360px;
  margin: 80px auto;
  background: white;
  padding: 30px;
  border-radius: 12px;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.08);
}

h2 {
  text-align: center;
  margin-bottom: 20px;
}

.form-item {
  margin-bottom: 16px;
}

label {
  display: block;
  margin-bottom: 6px;
}

input {
  width: 100%;
  padding: 8px;
  box-sizing: border-box;
}

button {
  width: 100%;
  padding: 10px;
  border: none;
  background: #409eff;
  color: white;
  border-radius: 6px;
  cursor: pointer;
}
</style>