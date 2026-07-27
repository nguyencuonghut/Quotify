import js from '@eslint/js'
import eslintConfigPrettier from 'eslint-config-prettier'
import pluginVue from 'eslint-plugin-vue'
import tseslint from 'typescript-eslint'

export default [
  {
    ignores: [
      'coverage/**',
      'dist/**',
      'node_modules/**',
      'playwright-report/**',
      'test-results/**',
    ],
  },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  ...pluginVue.configs['flat/recommended'],
  {
    files: ['**/*.{ts,vue}'],
    languageOptions: {
      parserOptions: {
        ecmaVersion: 'latest',
        parser: tseslint.parser,
        sourceType: 'module',
      },
      globals: {
        console: 'readonly',
        document: 'readonly',
        localStorage: 'readonly',
        navigator: 'readonly',
        process: 'readonly',
        window: 'readonly',
      },
    },
    rules: {
      '@typescript-eslint/consistent-type-imports': 'error',
      'vue/block-order': [
        'error',
        {
          order: ['template', 'script', 'style'],
        },
      ],
      'vue/html-self-closing': [
        'error',
        {
          html: {
            normal: 'always',
            void: 'always',
            component: 'always',
          },
          math: 'always',
          svg: 'always',
        },
      ],
      'vue/max-attributes-per-line': [
        'error',
        {
          multiline: 1,
          singleline: 3,
        },
      ],
      'vue/multi-word-component-names': 'off',
    },
  },
  {
    files: ['tests/**/*.{ts,tsx}'],
    languageOptions: {
      globals: {
        beforeEach: 'readonly',
        describe: 'readonly',
        expect: 'readonly',
        it: 'readonly',
      },
    },
  },
  {
    files: ['scripts/**/*.mjs'],
    languageOptions: {
      globals: {
        URL: 'readonly',
        console: 'readonly',
        process: 'readonly',
      },
    },
  },
  eslintConfigPrettier,
]
