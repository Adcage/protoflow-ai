/** 知识库管理 API（手动维护，非自动生成） */

import myAxios from '@/request'

const KNOWLEDGE_BASE = '/v1/admin/knowledge'

export interface LibraryVO {
  slug: string
  display_name: string
  description: string
  doc_count: number
  indexed_at: string | null
  has_index_json: boolean
}

export interface DocumentVO {
  id: string
  library_slug: string
  filename: string
  file_size: number
  file_hash: string
  chunk_count: number
  indexed_at: string | null
}

export interface RagStatusVO {
  enabled: boolean
  embedding_configured: boolean
  embedding_model: string
  total_libraries: number
  total_documents: number
  total_chunks: number
  last_indexed_at: string | null
  error_message: string
}

export interface ReindexResponse {
  success: boolean
  message: string
  documents_indexed: number
}

export interface DeleteResponse {
  success: boolean
  message: string
}

/** 获取 RAG 状态 */
export async function getRagStatus() {
  return myAxios.get<RagStatusVO>(`${KNOWLEDGE_BASE}/status`)
}

/** 列出文档库 */
export async function listLibraries() {
  return myAxios.get<LibraryVO[]>(`${KNOWLEDGE_BASE}/libraries`)
}

/** 列出文档 */
export async function listDocuments(library?: string) {
  const params: Record<string, string> = {}
  if (library) params.library = library
  return myAxios.get<DocumentVO[]>(`${KNOWLEDGE_BASE}/documents`, { params })
}

/** 上传文档 */
export async function uploadDocument(library: string, file: File) {
  const formData = new FormData()
  formData.append('library', library)
  formData.append('file', file)
  return myAxios.post<DocumentVO>(`${KNOWLEDGE_BASE}/upload`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

/** 删除文档 */
export async function deleteDocument(library: string, filename: string) {
  return myAxios.delete<DeleteResponse>(`${KNOWLEDGE_BASE}/document`, {
    params: { library, filename },
  })
}

/** 创建文档库 */
export async function createLibrary(slug: string, displayName?: string, description?: string) {
  return myAxios.post<LibraryVO>(`${KNOWLEDGE_BASE}/library`, null, {
    params: { slug, display_name: displayName, description },
  })
}

/** 删除文档库 */
export async function deleteLibrary(slug: string) {
  return myAxios.delete<DeleteResponse>(`${KNOWLEDGE_BASE}/library`, {
    params: { slug },
  })
}

/** 触发重建索引 */
export async function triggerReindex() {
  return myAxios.post<ReindexResponse>(`${KNOWLEDGE_BASE}/reindex`)
}
