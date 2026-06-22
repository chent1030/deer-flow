import { useState } from 'react';
import { Modal, Descriptions, Radio, Input, Button, message, Space } from 'antd';
import { AuditOutlined, DownloadOutlined } from '@ant-design/icons';
import { useAutoReviewSkill, useReviewSkill } from '../../hooks/useSkills';
import { downloadSkill } from '../../api/skills';
import type { Skill } from '../../types';

const { TextArea } = Input;

function getApiErrorMessage(error: unknown, fallback: string): string {
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
  }
  return fallback;
}

interface SkillReviewModalProps {
  skill: Skill;
  open: boolean;
  onClose: () => void;
}

export default function SkillReviewModal({ skill, open, onClose }: SkillReviewModalProps) {
  const [action, setAction] = useState<'approve' | 'reject'>('approve');
  const [comment, setComment] = useState('');
  const [reviewSkillName, setReviewSkillName] = useState('skill-reviewer');
  const reviewMut = useReviewSkill();
  const autoReviewMut = useAutoReviewSkill();

  const handleDownload = async () => {
    try {
      await downloadSkill(skill.id, skill.name);
      message.success('下载已开始');
    } catch {
      message.error('下载失败');
    }
  };

  const handleSubmit = async () => {
    try {
      await reviewMut.mutateAsync({ id: skill.id, action, comment });
      message.success(action === 'approve' ? 'Skill 已通过' : 'Skill 已驳回');
      onClose();
      setComment('');
      setAction('approve');
    } catch (e: unknown) {
      message.error(getApiErrorMessage(e, '审核失败'));
    }
  };

  const handleAutoReview = async () => {
    try {
      const reviewedSkill = await autoReviewMut.mutateAsync({ id: skill.id, reviewSkillName });
      const reviewComment = reviewedSkill.review_comment?.trim();
      const resultLabel = reviewedSkill.status === 'rejected' ? '已驳回' : reviewedSkill.status === 'approved' ? '已通过' : '已完成';
      message.success(reviewComment ? `自动审核${resultLabel}：${reviewComment}` : `自动审核${resultLabel}`);
      onClose();
      setComment('');
      setAction('approve');
    } catch (e: unknown) {
      message.error(getApiErrorMessage(e, '自动审核失败'));
    }
  };

  return (
    <Modal
      title="审核 Skill"
      open={open}
      onCancel={onClose}
      footer={
        <Space>
          <Button icon={<DownloadOutlined />} onClick={handleDownload}>
            下载验证
          </Button>
          <Button
            icon={<AuditOutlined />}
            loading={autoReviewMut.isPending}
            disabled={!reviewSkillName.trim()}
            onClick={handleAutoReview}
          >
            自动审核
          </Button>
          <Button onClick={onClose}>取消</Button>
          <Button
            type="primary"
            loading={reviewMut.isPending}
            danger={action === 'reject'}
            onClick={handleSubmit}
          >
            {action === 'approve' ? '通过' : '驳回'}
          </Button>
        </Space>
      }
    >
      <Descriptions column={1} bordered size="small">
        <Descriptions.Item label="名称">{skill.name}</Descriptions.Item>
        <Descriptions.Item label="版本">{skill.version}</Descriptions.Item>
        <Descriptions.Item label="描述">{skill.description || '-'}</Descriptions.Item>
        <Descriptions.Item label="作者">{skill.author_name || skill.author_id}</Descriptions.Item>
        <Descriptions.Item label="大小">{(skill.file_size / 1024).toFixed(1)} KB</Descriptions.Item>
      </Descriptions>
      <div style={{ marginTop: 16 }}>
        <Radio.Group value={action} onChange={(e) => setAction(e.target.value)}>
          <Radio value="approve">通过</Radio>
          <Radio value="reject">驳回</Radio>
        </Radio.Group>
      </div>
      <div style={{ marginTop: 12 }}>
        <Input
          placeholder="审核 Skill 名称"
          value={reviewSkillName}
          onChange={(e) => setReviewSkillName(e.target.value)}
          style={{ marginBottom: 12 }}
        />
        <TextArea
          rows={3}
          placeholder="审核意见（可选）"
          value={comment}
          onChange={(e) => setComment(e.target.value)}
        />
      </div>
    </Modal>
  );
}
