import { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { FileText, ExternalLink } from 'lucide-react';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1';

interface Attachment {
  id: number;
  file_name: string;
  file_path: string;
  file_size: number;
  file_url: string | null;
  attachment_type: string;
  created_at: string;
}

interface ContractAttachmentsProps {
  contractId: number;
}

export default function ContractAttachments({ contractId }: ContractAttachmentsProps) {
  const [attachments, setAttachments] = useState<Attachment[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadAttachments();
  }, [contractId]);

  const loadAttachments = async () => {
    try {
      const token = localStorage.getItem('token');
      const response = await fetch(`${API_BASE_URL}/contracts/${contractId}/attachments`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
      
      if (!response.ok) {
        throw new Error('加载附件失败');
      }
      
      const data = await response.json();
      setAttachments(data.attachments || []);
    } catch (error) {
      console.error('加载附件失败:', error);
    } finally {
      setLoading(false);
    }
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(2) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(2) + ' MB';
  };

  const getFileExtension = (filename: string): string => {
    const parts = filename.split('.');
    return parts.length > 1 ? parts[parts.length - 1].toLowerCase() : '';
  };

  const getFileIcon = (filename: string) => {
    const ext = getFileExtension(filename);
    const iconClass = "h-5 w-5";
    
    if (['pdf'].includes(ext)) {
      return <FileText className={`${iconClass} text-red-600`} />;
    } else if (['doc', 'docx'].includes(ext)) {
      return <FileText className={`${iconClass} text-blue-600`} />;
    } else if (['xls', 'xlsx'].includes(ext)) {
      return <FileText className={`${iconClass} text-green-600`} />;
    }
    return <FileText className={`${iconClass} text-gray-600`} />;
  };

  const handleOpenUrl = (url: string) => {
    window.open(url, '_blank');
  };

  if (loading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>合同附件</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-center py-4 text-gray-500">加载中...</div>
        </CardContent>
      </Card>
    );
  }

  if (attachments.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>合同附件</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-center py-4 text-gray-500">暂无附件</div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>合同附件 ({attachments.length})</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-2">
          {attachments.map((attachment) => (
            <div
              key={attachment.id}
              className="flex items-center justify-between p-3 border rounded hover:bg-gray-50"
            >
              <div className="flex items-center gap-3 flex-1">
                {getFileIcon(attachment.file_name)}
                <div className="flex-1 min-w-0">
                  <div className="font-medium truncate">
                    {attachment.file_name}
                  </div>
                  <div className="text-sm text-gray-500">
                    {formatFileSize(attachment.file_size)} • {' '}
                    {new Date(attachment.created_at).toLocaleDateString()}
                  </div>
                </div>
              </div>
              <div className="flex gap-2">
                {attachment.file_url && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleOpenUrl(attachment.file_url!)}
                    title="在OA系统中打开"
                  >
                    <ExternalLink className="h-4 w-4" />
                  </Button>
                )}
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
