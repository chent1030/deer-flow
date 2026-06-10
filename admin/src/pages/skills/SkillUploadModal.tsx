import { useState, useRef } from 'react';
import { Modal, Form, Input, Upload, message, List } from 'antd';
import { InboxOutlined } from '@ant-design/icons';
import JSZip from 'jszip';
import { useUploadSkill } from '../../hooks/useSkills';

const { Dragger } = Upload;
const { TextArea } = Input;

type SkillUploadFile = File & {
  fullPath?: string;
};

interface SkillUploadFormValues {
  name: string;
  description?: string;
}

interface SkillUploadModalProps {
  open: boolean;
  onClose: () => void;
}

function getFilePath(file: SkillUploadFile): string {
  return file.fullPath || file.webkitRelativePath || file.name;
}

function getErrorMessage(error: unknown, fallback: string): string {
  if (typeof error === 'object' && error !== null) {
    const response = Reflect.get(error, 'response');
    if (typeof response === 'object' && response !== null) {
      const data = Reflect.get(response, 'data');
      if (typeof data === 'object' && data !== null) {
        const detail = Reflect.get(data, 'detail');
        if (typeof detail === 'string' && detail) {
          return detail;
        }
      }
    }
    const message = Reflect.get(error, 'message');
    if (typeof message === 'string' && message) {
      return message;
    }
  }
  return fallback;
}

export default function SkillUploadModal({ open, onClose }: SkillUploadModalProps) {
  const [form] = Form.useForm();
  const [files, setFiles] = useState<SkillUploadFile[]>([]);
  const [loading, setLoading] = useState(false);
  const uploadMut = useUploadSkill();
  const folderRef = useRef<HTMLInputElement>(null);

  const handleFolderSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const fileList = e.target.files;
    if (!fileList || fileList.length === 0) return;
    const arr = Array.from(fileList) as SkillUploadFile[];
    setFiles(arr);
    const hasSkillMd = arr.some(
      (f) => f.webkitRelativePath.endsWith('SKILL.md') || f.name === 'SKILL.md',
    );
    if (!hasSkillMd) {
      message.warning('未找到 SKILL.md — Skill 必须包含 SKILL.md');
    }
    const folderName = arr[0].webkitRelativePath.split('/')[0];
    if (folderName && !form.getFieldValue('name')) {
      form.setFieldsValue({ name: folderName });
    }
  };

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    const items = e.dataTransfer.items;
    if (!items) return;
    const allFiles: SkillUploadFile[] = [];
    const entries: FileSystemEntry[] = [];
    for (let i = 0; i < items.length; i++) {
      const entry = items[i].webkitGetAsEntry?.();
      if (entry) entries.push(entry);
    }
    if (entries.length === 0) return;
    for (const entry of entries) {
      await readEntry(entry, '', allFiles);
    }
    if (allFiles.length === 0) return;
    setFiles(allFiles);
    const hasSkillMd = allFiles.some(
      (f) => f.fullPath?.endsWith('SKILL.md') || f.name === 'SKILL.md',
    );
    if (!hasSkillMd) {
      message.warning('未找到 SKILL.md — Skill 必须包含 SKILL.md');
    }
    const firstPath = getFilePath(allFiles[0]);
    const folderName = firstPath.startsWith('/') ? firstPath.split('/')[1] : firstPath.split('/')[0];
    if (folderName && !form.getFieldValue('name')) {
      form.setFieldsValue({ name: folderName });
    }
  };

  const readEntry = async (entry: FileSystemEntry, path: string, result: SkillUploadFile[]): Promise<void> => {
    if (entry.isFile) {
      const fileEntry = entry as FileSystemFileEntry;
      await new Promise<void>((resolve) => {
        fileEntry.file((file) => {
          Object.defineProperty(file, 'fullPath', { value: path + file.name });
          result.push(file as SkillUploadFile);
          resolve();
        });
      });
    } else if (entry.isDirectory) {
      const dirEntry = entry as FileSystemDirectoryEntry;
      const reader = dirEntry.createReader();
      await new Promise<void>((resolve) => {
        const readBatch = () => {
          reader.readEntries(async (entries) => {
            if (entries.length === 0) {
              resolve();
              return;
            }
            for (const e of entries) {
              await readEntry(e, path + dirEntry.name + '/', result);
            }
            readBatch();
          });
        };
        readBatch();
      });
    }
  };

  const buildZip = async (): Promise<Blob> => {
    const zip = new JSZip();
    for (const file of files) {
      const fullPath = getFilePath(file);
      const entryPath = fullPath.includes('/') ? fullPath.split('/').slice(1).join('/') : fullPath;
      if (!entryPath) continue;
      zip.file(entryPath, file);
    }
    return zip.generateAsync({ type: 'blob' });
  };

  const onFinish = async (values: SkillUploadFormValues) => {
    if (files.length === 0) {
      message.error('请选择 Skill 文件夹');
      return;
    }
    setLoading(true);
    try {
      const zipBlob = await buildZip();
      const zipFile = new File([zipBlob], `${values.name}.zip`, { type: 'application/zip' });
      await uploadMut.mutateAsync({
        file: zipFile,
        name: values.name,
        description: values.description || '',
      });
      message.success('Skill 已上传');
      onClose();
      form.resetFields();
      setFiles([]);
    } catch (e: unknown) {
      message.error(getErrorMessage(e, '上传失败'));
    } finally {
      setLoading(false);
    }
  };

  const rootItems = files.length > 0
    ? [...new Set(files.map((f) => {
        const p = getFilePath(f);
        const parts = p.split('/');
        return parts.length > 2 ? parts.slice(0, 3).join('/') : parts.join('/');
      }))]
    : [];

  return (
    <Modal
      title="上传 Skill"
      open={open}
      onCancel={() => { onClose(); form.resetFields(); setFiles([]); }}
      onOk={() => form.submit()}
      confirmLoading={loading || uploadMut.isPending}
      width={600}
    >
      <Form form={form} layout="vertical" onFinish={onFinish}>
        <Form.Item name="name" label="Skill 名称" rules={[{ required: true }]}>
          <Input />
        </Form.Item>
        <Form.Item label="版本">
          <Input value="自动生成；同名 Skill 再次上传时自动递增" disabled />
        </Form.Item>
        <Form.Item name="description" label="描述">
          <TextArea rows={3} />
        </Form.Item>
        <Form.Item label="Skill 文件夹" required>
          <input
            ref={folderRef}
            type="file"
            webkitdirectory=""
            directory=""
            style={{ display: 'none' }}
            onChange={handleFolderSelect}
          />
          <div
            onDrop={handleDrop}
            onDragOver={(e) => { e.preventDefault(); e.stopPropagation(); }}
            onDragEnter={(e) => { e.preventDefault(); e.stopPropagation(); }}
          >
            <Dragger
              showUploadList={false}
              beforeUpload={() => false}
              customRequest={() => {}}
              onClick={() => folderRef.current?.click()}
            >
              <p className="ant-upload-drag-icon"><InboxOutlined /></p>
              <p className="ant-upload-text">拖拽 Skill 文件夹到此处，或点击选择</p>
              <p className="ant-upload-hint">必须包含 SKILL.md</p>
            </Dragger>
          </div>
          {files.length > 0 && (
            <div style={{ marginTop: 8 }}>
              <div style={{ marginBottom: 4, color: '#666' }}>{files.length} 个文件已选择</div>
              <List
                size="small"
                bordered
                dataSource={rootItems.slice(0, 15)}
                renderItem={(item) => <List.Item style={{ padding: '2px 8px', fontSize: 12 }}>{item}</List.Item>}
                style={{ maxHeight: 150, overflow: 'auto' }}
              />
              {rootItems.length > 15 && <div style={{ color: '#999', fontSize: 12, marginTop: 4 }}>... 等</div>}
            </div>
          )}
        </Form.Item>
      </Form>
    </Modal>
  );
}
