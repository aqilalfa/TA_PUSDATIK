<template>
  <button class="scroll-to-top" @click="$emit('click')" aria-label="Kembali ke atas">
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
      <path d="M8 12V4M4 8l4-4 4 4" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
    </svg>
  </button>
</template>

<script setup>
defineEmits(['click'])
</script>

<style scoped>
.scroll-to-top {
  position: fixed;
  bottom: 90px;
  right: 28px;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: var(--color-navy);
  border: none;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 2px 8px rgba(26, 58, 107, 0.2);
  transition: background 0.15s;
}

.scroll-to-top:hover {
  background: var(--color-navy-hover);
}
</style>
