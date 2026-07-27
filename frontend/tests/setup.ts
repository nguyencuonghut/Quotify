import { config } from '@vue/test-utils'

config.global.stubs = {
  Button: {
    props: ['label'],
    template: '<button><slot />{{ label }}</button>',
  },
  Card: {
    template: '<article><slot name="title" /><slot name="content" /></article>',
  },
  Column: true,
  DataTable: {
    props: ['value'],
    template:
      '<div><slot /><div data-testid="row-count">{{ value?.length ?? 0 }}</div></div>',
  },
  InputText: {
    props: ['modelValue'],
    emits: ['update:modelValue'],
    template:
      '<input :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
  },
  Password: {
    props: ['modelValue'],
    emits: ['update:modelValue'],
    template:
      '<input :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
  },
  RouterLink: {
    props: ['to'],
    template: '<a :href="to"><slot /></a>',
  },
  Tag: {
    props: ['value'],
    template: '<span>{{ value }}</span>',
  },
  ToggleSwitch: {
    props: ['modelValue'],
    emits: ['update:modelValue'],
    template:
      '<input type="checkbox" :checked="modelValue" @change="$emit(\'update:modelValue\', !modelValue)" />',
  },
}
