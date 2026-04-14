import { useRef, useState } from 'react';

import { api, type StructuredCardImportReport, type StructuredCardType } from '../api/client';

type Props = {
  projectId: string;
  cardType: StructuredCardType;
  title: string;
  showJsonControls?: boolean;
  onImported?: () => Promise<void> | void;
};

function downloadBlob(blob: Blob, fileName: string) {
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = fileName;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(url);
}

function ReportView({ report }: { report: StructuredCardImportReport | null }) {
  if (!report) return null;
  return <div className="panel">
    <h4>导入结果</h4>
    <p>总行数：{report.total_rows}，新建：{report.created_count}，跳过：{report.skipped_count}，错误：{report.error_count}</p>
    {report.skipped.length > 0 && <ul>
      {report.skipped.slice(0, 5).map((item) => <li key={`${item.row}-${item.reason}`}>第 {item.row} 行：{item.reason}</li>)}
    </ul>}
    {report.errors.length > 0 && <ul>
      {report.errors.slice(0, 5).map((item) => <li key={`${item.row}-${item.field}-${item.message}`}>第 {item.row} 行，字段 {item.field}：{item.message}</li>)}
    </ul>}
  </div>;
}

export function StructuredCardImportExportPanel({ projectId, cardType, title, showJsonControls = false, onImported }: Props) {
  const csvImportRef = useRef<HTMLInputElement | null>(null);
  const jsonImportRef = useRef<HTMLInputElement | null>(null);
  const [error, setError] = useState('');
  const [report, setReport] = useState<StructuredCardImportReport | null>(null);
  const [busy, setBusy] = useState(false);

  const runSafely = async (task: () => Promise<void>) => {
    setBusy(true);
    setError('');
    try {
      await task();
    } catch {
      setError('操作失败，请检查文件格式后重试。');
    } finally {
      setBusy(false);
    }
  };

  return <div className="panel">
    <h3>{title}</h3>
    <p>支持 CSV 导入导出与模板下载。导入仅更新基础卡槽，不会自动写入 Canon，也不会生成 ChangeSet。</p>
    <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
      <button type="button" disabled={busy} onClick={() => runSafely(async () => {
        const blob = await api.downloadStructuredCardsCsvTemplate(projectId, cardType);
        downloadBlob(blob, `${cardType}-template.csv`);
      })}>下载 CSV 模板</button>
      <button type="button" disabled={busy} onClick={() => runSafely(async () => {
        const blob = await api.exportStructuredCardsCsv(projectId, cardType);
        downloadBlob(blob, `${cardType}-export.csv`);
      })}>导出 CSV</button>
      <button type="button" disabled={busy} onClick={() => csvImportRef.current?.click()}>导入 CSV</button>
      <input
        ref={csvImportRef}
        type="file"
        accept=".csv"
        style={{ display: 'none' }}
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (!file) return;
          void runSafely(async () => {
            const result = await api.importStructuredCardsCsv(projectId, cardType, file);
            setReport(result);
            if (onImported) await onImported();
          });
          e.currentTarget.value = '';
        }}
      />

      {showJsonControls && <>
        <button type="button" disabled={busy} onClick={() => runSafely(async () => {
          const blob = await api.exportStructuredCardsJson(projectId);
          downloadBlob(blob, `${projectId}-structured-cards.json`);
        })}>导出全部 JSON</button>
        <button type="button" disabled={busy} onClick={() => jsonImportRef.current?.click()}>导入 JSON</button>
        <input
          ref={jsonImportRef}
          type="file"
          accept=".json"
          style={{ display: 'none' }}
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (!file) return;
            void runSafely(async () => {
              const result = await api.importStructuredCardsJson(projectId, file);
              setReport(result);
              if (onImported) await onImported();
            });
            e.currentTarget.value = '';
          }}
        />
      </>}
    </div>
    {error && <p>{error}</p>}
    <ReportView report={report} />
  </div>;
}
