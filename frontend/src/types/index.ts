export type ContractType = 
  | '采购合同'
  | '销售合同'
  | '人力合同'
  | 'NDA保密协议'
  | '租赁合同'
  | '服务合同'
  | '投资协议'
  | '其他'

export type Department = 
  | '科技中心'
  | '财务中心'
  | '法务合规中心'
  | '风控中心'
  | '普惠金融'
  | '人力行政中心'
  | '其他'

export type ContractStatus = 
  | '待审核'
  | '已签署'
  | '执行中'
  | '已到期'
  | '已终止'

export interface Contract {
  id: string
  contractNumber: string
  title: string
  type: ContractType
  department: Department
  status: ContractStatus
  parties: string[]
  amount: number | null
  currency: string
  signedDate: string
  startDate: string
  endDate: string
  createdAt: string
  updatedAt: string
  fileUrl: string
  filePath?: string
  originalFilename?: string
  riskLevel?: 'low' | 'medium' | 'high'
  summary?: string
  riskAnalysis?: string
  extractedData?: string
  // OA系统字段
  source?: string
  oaId?: string
  applicant?: string
  position?: string
  company?: string
  counterparty?: string
  counterpartyContact?: string
  counterpartyAddress?: string
  paymentType?: string
  copies?: string
}

export interface ContractStats {
  total: number
  thisMonth: number
  pendingRenewal: number
  pendingReview: number
  byType: Record<ContractType, number>
  byDepartment: Record<Department, number>
  byStatus: Record<ContractStatus, number>
  monthlyTrend: { month: string; count: number }[]
}

export interface RiskAnalysis {
  contractId: string
  overallRisk: 'low' | 'medium' | 'high'
  riskPoints: {
    category: string
    description: string
    severity: 'low' | 'medium' | 'high'
    suggestion: string
  }[]
  summary: string
  generatedAt: string
}

export interface SearchResult {
  contracts: Contract[]
  total: number
  query: string
  suggestions?: string[]
}

export interface APIKey {
  id: string
  name: string
  key: string
  createdAt: string
  lastUsed: string | null
  status: 'active' | 'inactive'
}

export interface MCPConfig {
  enabled: boolean
  serverUrl: string
  connected: boolean
  lastConnected: string | null
  tools: string[]
}
