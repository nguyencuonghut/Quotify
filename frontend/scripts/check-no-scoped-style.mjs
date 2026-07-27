import { readdir, readFile } from 'node:fs/promises'
import path from 'node:path'

const rootDir = new URL('../src/', import.meta.url)
const vueFiles = []

async function walk(dirUrl) {
  const entries = await readdir(dirUrl, { withFileTypes: true })

  for (const entry of entries) {
    const entryUrl = new URL(
      `${entry.name}${entry.isDirectory() ? '/' : ''}`,
      dirUrl,
    )

    if (entry.isDirectory()) {
      await walk(entryUrl)
      continue
    }

    if (entry.isFile() && entry.name.endsWith('.vue')) {
      vueFiles.push(entryUrl)
    }
  }
}

await walk(rootDir)

const violations = []

for (const fileUrl of vueFiles) {
  const content = await readFile(fileUrl, 'utf8')

  if (/<style\b/i.test(content)) {
    violations.push(path.relative(process.cwd(), fileUrl.pathname))
  }
}

if (violations.length > 0) {
  console.error('Do not use <style> blocks in Vue SFC files:')
  for (const file of violations) {
    console.error(`- ${file}`)
  }
  process.exit(1)
}
