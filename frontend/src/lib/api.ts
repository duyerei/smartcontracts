const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1'

interface ApiResponse<T> {
  data?: T
  error?: string
}

export interface AgentOperation {
  action: 'list_contracts' | 'get_contract' | 'delete_contract' | 'reparse_contract' | 'consult'
  contract_id?: number
}

export interface AgentChatResponse {
  reply: string
  requires_confirmation?: boolean
  operation?: AgentOperation
  data?: Record<string, unknown>[]
  conversation_id?: string
  provider?: 'ark' | 'appbuilder' | 'qianfan' | 'rule'
  error_detail?: string
}

function transformContract(apiContract: Record<string, unknown>): Record<string, unknown> {
  // 解析 parties 字段
  let parties: string[] = []
  if (typeof apiContract.parties === 'string') {
    try {
      const parsed = JSON.parse(apiContract.parties)
      parties = Array.isArray(parsed) ? parsed : [apiContract.parties]
    } catch {
      // 如果解析失败，尝试按逗号分割
      parties = apiContract.parties.split(',').map(p => p.trim()).filter(p => p)
    }
  } else if (Array.isArray(apiContract.parties)) {
    parties = apiContract.parties
  }
  
  // 过滤掉无效值
  parties = parties.filter(p => p && p !== 'null' && p !== '待填写' && String(p).trim() !== '')
  
  return {
    id: String(apiContract.id),
    contractNumber: apiContract.contract_number,
    title: apiContract.title,
    type: apiContract.contract_type,
    department: apiContract.department,
    status: apiContract.status,
    parties: parties,
    amount: apiContract.amount,
    currency: apiContract.currency,
    signedDate: apiContract.signed_date ? String(apiContract.signed_date).split('T')[0] : '',
    startDate: apiContract.start_date ? String(apiContract.start_date).split('T')[0] : '',
    endDate: apiContract.end_date ? String(apiContract.end_date).split('T')[0] : '',
    createdAt: apiContract.created_at ? String(apiContract.created_at).replace('T', ' ').split('.')[0] : '',
    updatedAt: apiContract.updated_at ? String(apiContract.updated_at).replace('T', ' ').split('.')[0] : '',
    fileUrl: `/api/v1/contracts/${apiContract.id}/download`,
    filePath: apiContract.file_path || '',
    originalFilename: apiContract.original_filename || '',
    riskLevel: apiContract.risk_level,
    summary: apiContract.summary,
    riskAnalysis: apiContract.risk_analysis,
    extractedData: apiContract.extracted_data,
    // OA系统字段
    source: apiContract.source,
    oaId: apiContract.oa_id,
    applicant: apiContract.applicant,
    position: apiContract.position,
    company: apiContract.company,
    counterparty: apiContract.counterparty,
    counterpartyContact: apiContract.counterparty_contact,
    counterpartyAddress: apiContract.counterparty_address,
    paymentType: apiContract.payment_type,
    copies: apiContract.copies,
    rawData: apiContract.raw_data,
    // 补充协议树形关系
    is_supplement_child: apiContract.is_supplement_child || false,
    supplement_children: Array.isArray(apiContract.supplement_children)
      ? (apiContract.supplement_children as Record<string, unknown>[]).map(transformContract)
      : [],
  }
}

async function fetchApi<T>(
  endpoint: string,
  options?: RequestInit
): Promise<ApiResponse<T>> {
  try {
    const token = localStorage.getItem('token')
    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...options?.headers,
      },
    })

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}))
      throw new Error(errorData.detail || `HTTP error ${response.status}`)
    }

    const data = await response.json()
    return { data }
  } catch (error) {
    console.error(`API Error [${endpoint}]:`, error)
    return { error: (error as Error).message }
  }
}

export const contractApi = {
  list: async (params?: {
    page?: number
    page_size?: number
    search?: string
    contract_type?: string
    department?: string
    status?: string
    sort_field?: string
    sort_order?: string
  }) => {
    const queryParams = new URLSearchParams()
    if (params?.page) queryParams.set('page', params.page.toString())
    if (params?.page_size) queryParams.set('page_size', params.page_size.toString())
    if (params?.search) queryParams.set('search', params.search)
    if (params?.contract_type) queryParams.set('contract_type', params.contract_type)
    if (params?.department) queryParams.set('department', params.department)
    if (params?.status) queryParams.set('status', params.status)
    if (params?.sort_field) queryParams.set('sort_field', params.sort_field)
    if (params?.sort_order) queryParams.set('sort_order', params.sort_order)

    const query = queryParams.toString()
    const result = await fetchApi<{ total: number; contracts: Record<string, unknown>[] }>(`/contracts${query ? `?${query}` : ''}`)
    
    if (result.data) {
      return {
        data: {
          total: result.data.total,
          contracts: result.data.contracts.map(transformContract),
        }
      }
    }
    return result
  },

  get: async (id: string) => {
    const result = await fetchApi<Record<string, unknown>>(`/contracts/${id}`)
    if (result.data) {
      return {
        data: transformContract(result.data)
      }
    }
    return result
  },

  upload: async (file: File, metadataHint?: string) => {
    const formData = new FormData()
    formData.append('file', file)
    if (metadataHint) {
      formData.append('metadata_hint', metadataHint)
    }

    try {
      const token = localStorage.getItem('token')
      const response = await fetch(`${API_BASE_URL}/contracts/upload`, {
        method: 'POST',
        headers: {
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: formData,
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.detail || `Upload failed`)
      }

      const data = await response.json()
      return { data }
    } catch (error) {
      console.error('Upload Error:', error)
      return { error: (error as Error).message }
    }
  },

  update: async (id: number, data: Record<string, unknown>) => {
    return fetchApi(`/contracts/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    })
  },

  delete: async (id: number) => {
    return fetchApi(`/contracts/${id}`, {
      method: 'DELETE',
    })
  },

  download: async (id: number) => {
    window.open(`${API_BASE_URL}/contracts/${id}/download`, '_blank')
  },

  analyze: async (id: number) => {
    return fetchApi(`/contracts/${id}/analyze`)
  },

  getText: async (id: number) => {
    return fetchApi(`/contracts/${id}/text`)
  },

  reparse: async (id: number, attachmentId?: number) => {
    const token = localStorage.getItem('token')
    const url = attachmentId ? `${API_BASE_URL}/contracts/${id}/reparse?attachment_id=${attachmentId}` : `${API_BASE_URL}/contracts/${id}/reparse`
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
    })
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}))
      throw new Error(errorData.detail || '重新解析失败')
    }
    return response.json()
  },

  analyzeAttachment: async (contractId: number, attachmentId: number) => {
    const token = localStorage.getItem('token')
    const response = await fetch(`${API_BASE_URL}/contracts/${contractId}/attachments/${attachmentId}/analyze`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
    })
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}))
      throw new Error(errorData.detail || '分析附件失败')
    }
    return response.json()
  },
}

export const agentApi = {
  chat: async (
    message: string,
    confirm = false,
    operation?: AgentOperation,
    conversationId?: string,
  ) => {
    return fetchApi<AgentChatResponse>('/agent/chat', {
      method: 'POST',
      body: JSON.stringify({
        message,
        confirm,
        operation,
        conversation_id: conversationId,
      }),
    })
  },

  chatStream: async (
    message: string,
    conversationId: string | undefined,
    onToken: (text: string) => void,
    onDone: (conversationId: string, provider: string) => void,
    onError: (detail: string) => void,
  ) => {
    try {
      const token = localStorage.getItem('token')
      const response = await fetch(`${API_BASE_URL}/agent/chat/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ message, conversation_id: conversationId }),
      })
      if (!response.ok || !response.body) {
        onError(`HTTP ${response.status}`)
        return
      }
      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let gotDone = false
      const processLine = (line: string) => {
        if (!line.startsWith('data: ')) return
        const jsonStr = line.slice(6).trim()
        if (!jsonStr) return
        try {
          const evt = JSON.parse(jsonStr)
          if (evt.event === 'token') {
            onToken(evt.data)
          } else if (evt.event === 'done') {
            gotDone = true
            onDone(evt.conversation_id || '', evt.provider || 'ark')
          } else if (evt.event === 'error') {
            onError(evt.error_detail || '未知错误')
          }
        } catch { /* skip bad JSON */ }
      }
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''
        for (const line of lines) {
          processLine(line)
        }
      }
      // 处理 buffer 中残留的最后一行
      if (buffer.trim()) {
        processLine(buffer.trim())
      }
      // 如果流结束但没收到 done 事件，也通知前端完成
      if (!gotDone) {
        onDone('', 'ark')
      }
    } catch (err) {
      onError((err as Error).message)
    }
  },
}

export const statsApi = {
  get: async () => {
    const result = await contractApi.list({ page: 1, page_size: 1 })
    if (result.error || !result.data) {
      return {
        total: 0,
        thisMonth: 0,
        pendingRenewal: 0,
        pendingReview: 0,
      }
    }

    const total = (result.data as { total: number }).total
    return {
      total,
      thisMonth: Math.floor(total * 0.05),
      pendingRenewal: Math.floor(total * 0.01),
      pendingReview: Math.floor(total * 0.03),
    }
  },
}

export interface PaymentRecord {
  id: number
  payment_theme: string
  payment_date?: string
  amount?: number
  operator?: string
  cost_center?: string
  project_name?: string
  contract_number?: string
  application_number?: string
  payment_reason?: string
  contract_id?: number
  description?: string
  file_path?: string
  file_size?: number
  created_at?: string
}

export const paymentManagementApi = {
  list: async (params: { page?: number; page_size?: number; search?: string } = {}) => {
    const searchParams = new URLSearchParams()
    if (params.page) searchParams.set('page', String(params.page))
    if (params.page_size) searchParams.set('page_size', String(params.page_size))
    if (params.search) searchParams.set('search', params.search)
    
    const result = await fetchApi<{ payments: PaymentRecord[]; total: number; page: number; page_size: number }>(
      `/payments/management/list?${searchParams.toString()}`
    )
    return result
  },
  
  get: async (id: number) => {
    const result = await fetchApi<PaymentRecord>(`/payments/management/${id}`)
    return result
  },
  
  linkContract: async (paymentId: number, contractId: number) => {
    const result = await fetchApi<{ message: string; contract: any }>(
      `/payments/management/${paymentId}/link-contract?contract_id=${contractId}`,
      { method: 'PUT' }
    )
    return result
  },
  
  getByContract: async (contractId: number) => {
    const result = await fetchApi<{ payments: PaymentRecord[]; total: number }>(
      `/payments/by-contract/${contractId}`
    )
    return result
  },

  importPdf: async (file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    try {
      const token = localStorage.getItem('token')
      const response = await fetch(`${API_BASE_URL}/payments/management/import-pdf`, {
        method: 'POST',
        headers: {
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: formData,
      })
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.detail || '导入失败')
      }
      return { data: await response.json() }
    } catch (error) {
      return { error: (error as Error).message }
    }
  },
}

export interface PartnerRecord {
  id: number
  name: string
  contact_name?: string
  contact_phone?: string
  address?: string
  bank_name?: string
  bank_account?: string
  notes?: string
  contract_count?: number
  created_at?: string
  updated_at?: string
  contracts?: any[]
  attachments?: any[]
}

export const partnerApi = {
  list: async (params: { page?: number; page_size?: number; search?: string } = {}) => {
    const sp = new URLSearchParams()
    if (params.page) sp.set('page', String(params.page))
    if (params.page_size) sp.set('page_size', String(params.page_size))
    if (params.search) sp.set('search', params.search)
    return fetchApi<{ partners: PartnerRecord[]; total: number }>(`/partners?${sp.toString()}`)
  },
  get: async (id: number) => fetchApi<PartnerRecord>(`/partners/${id}`),
  create: async (data: Partial<PartnerRecord>) =>
    fetchApi<{ id: number; message: string }>('/partners', { method: 'POST', body: JSON.stringify(data) }),
  update: async (id: number, data: Partial<PartnerRecord>) =>
    fetchApi<{ message: string }>(`/partners/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  delete: async (id: number) =>
    fetchApi<{ message: string }>(`/partners/${id}`, { method: 'DELETE' }),
  syncFromContracts: async () =>
    fetchApi<{ message: string }>('/partners/sync-from-contracts'),
  uploadAttachment: async (partnerId: number, file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    const token = localStorage.getItem('token')
    const response = await fetch(`${API_BASE_URL}/partners/${partnerId}/attachments`, {
      method: 'POST',
      headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      body: formData,
    })
    if (!response.ok) {
      const err = await response.json().catch(() => ({}))
      throw new Error(err.detail || '上传失败')
    }
    return response.json()
  },
  deleteAttachment: async (partnerId: number, attId: number) =>
    fetchApi<{ message: string }>(`/partners/${partnerId}/attachments/${attId}`, { method: 'DELETE' }),
}
