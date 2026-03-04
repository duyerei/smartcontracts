import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Upload, CheckCircle, XCircle, AlertCircle } from 'lucide-react';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1';

interface ImportResult {
  success: boolean;
  imported: number;
  skipped: number;
  failed: number;
  errors: Array<{
    contract_number: string;
    contract_name: string;
    error: string;
  }>;
  details: {
    contracts: Array<{
      id: number;
      contract_number: string;
      title: string;
    }>;
    attachments: number;
  };
}

export default function ImportContracts() {
  const navigate = useNavigate();
  const [file, setFile] = useState<File | null>(null);
  const [importing, setImporting] = useState(false);
  const [result, setResult] = useState<ImportResult | null>(null);
  const [error, setError] = useState<string>('');

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0];
    if (selectedFile) {
      if (selectedFile.name.endsWith('.json')) {
        setFile(selectedFile);
        setError('');
        setResult(null);
      } else {
        setError('请选择JSON格式的文件');
        setFile(null);
      }
    }
  };

  const handleImport = async () => {
    if (!file) {
      setError('请先选择文件');
      return;
    }

    setImporting(true);
    setError('');
    setResult(null);

    try {
      const fileContent = await file.text();
      const contracts = JSON.parse(fileContent);

      const token = localStorage.getItem('token');
      const response = await fetch(`${API_BASE_URL}/contracts/import`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          contracts: contracts,
          skip_duplicates: true,
          update_existing: false
        })
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || '导入失败');
      }

      const result = await response.json();
      setResult(result);
    } catch (err: any) {
      setError(err.message || '导入失败');
    } finally {
      setImporting(false);
    }
  };

  return (
    <div className="container mx-auto p-6">
      <div className="mb-6">
        <h1 className="text-3xl font-bold">OA合同导入</h1>
        <p className="text-gray-600 mt-2">从OA系统批量导入合同数据</p>
      </div>

      <div className="grid gap-6">
        {/* 上传区域 */}
        <Card>
          <CardHeader>
            <CardTitle>选择导入文件</CardTitle>
            <CardDescription>
              支持JSON格式的合同数据文件
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="flex items-center gap-4">
                <input
                  type="file"
                  accept=".json"
                  onChange={handleFileChange}
                  className="flex-1"
                  disabled={importing}
                />
                <Button
                  onClick={handleImport}
                  disabled={!file || importing}
                  className="min-w-[120px]"
                >
                  {importing ? (
                    <>
                      <Upload className="mr-2 h-4 w-4 animate-spin" />
                      导入中...
                    </>
                  ) : (
                    <>
                      <Upload className="mr-2 h-4 w-4" />
                      开始导入
                    </>
                  )}
                </Button>
              </div>

              {file && !importing && !result && (
                <div className="text-sm text-gray-600">
                  已选择: {file.name} ({(file.size / 1024).toFixed(2)} KB)
                </div>
              )}

              {error && (
                <div className="flex items-center gap-2 text-red-600 bg-red-50 p-3 rounded">
                  <XCircle className="h-5 w-5" />
                  <span>{error}</span>
                </div>
              )}
            </div>
          </CardContent>
        </Card>

        {/* 导入结果 */}
        {result && (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                {result.success ? (
                  <>
                    <CheckCircle className="h-6 w-6 text-green-600" />
                    导入完成
                  </>
                ) : (
                  <>
                    <AlertCircle className="h-6 w-6 text-yellow-600" />
                    导入完成（部分失败）
                  </>
                )}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {/* 统计信息 */}
                <div className="grid grid-cols-4 gap-4">
                  <div className="bg-green-50 p-4 rounded">
                    <div className="text-2xl font-bold text-green-600">
                      {result.imported}
                    </div>
                    <div className="text-sm text-gray-600">成功导入</div>
                  </div>
                  <div className="bg-blue-50 p-4 rounded">
                    <div className="text-2xl font-bold text-blue-600">
                      {result.details.attachments}
                    </div>
                    <div className="text-sm text-gray-600">附件数量</div>
                  </div>
                  <div className="bg-yellow-50 p-4 rounded">
                    <div className="text-2xl font-bold text-yellow-600">
                      {result.skipped}
                    </div>
                    <div className="text-sm text-gray-600">跳过（重复）</div>
                  </div>
                  <div className="bg-red-50 p-4 rounded">
                    <div className="text-2xl font-bold text-red-600">
                      {result.failed}
                    </div>
                    <div className="text-sm text-gray-600">导入失败</div>
                  </div>
                </div>

                {/* 成功导入的合同列表 */}
                {result.details.contracts.length > 0 && (
                  <div>
                    <h3 className="font-semibold mb-2">成功导入的合同：</h3>
                    <div className="max-h-60 overflow-y-auto border rounded p-2">
                      {result.details.contracts.map((contract) => (
                        <div
                          key={contract.id}
                          className="flex items-center justify-between py-2 border-b last:border-b-0 hover:bg-gray-50"
                        >
                          <div>
                            <div className="font-medium">{contract.title}</div>
                            <div className="text-sm text-gray-600">
                              {contract.contract_number}
                            </div>
                          </div>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => navigate(`/contracts/${contract.id}`)}
                          >
                            查看详情
                          </Button>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* 错误列表 */}
                {result.errors.length > 0 && (
                  <div>
                    <h3 className="font-semibold mb-2 text-red-600">
                      导入失败的合同：
                    </h3>
                    <div className="max-h-60 overflow-y-auto border rounded p-2 bg-red-50">
                      {result.errors.map((err, index) => (
                        <div key={index} className="py-2 border-b last:border-b-0">
                          <div className="font-medium">{err.contract_name}</div>
                          <div className="text-sm text-gray-600">
                            {err.contract_number}
                          </div>
                          <div className="text-sm text-red-600 mt-1">
                            错误: {err.error}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* 操作按钮 */}
                <div className="flex gap-4">
                  <Button onClick={() => navigate('/contracts')}>
                    查看合同列表
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() => {
                      setFile(null);
                      setResult(null);
                      setError('');
                    }}
                  >
                    继续导入
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {/* 使用说明 */}
        <Card>
          <CardHeader>
            <CardTitle>使用说明</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2 text-sm text-gray-600">
              <p>1. 准备JSON格式的合同数据文件</p>
              <p>2. 点击"选择文件"按钮，选择要导入的JSON文件</p>
              <p>3. 点击"开始导入"按钮，系统将自动导入合同数据</p>
              <p>4. 导入完成后，可以查看导入结果和错误信息</p>
              <p className="text-yellow-600 mt-4">
                注意：系统会自动跳过已存在的合同（根据OA系统ID判断）
              </p>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
