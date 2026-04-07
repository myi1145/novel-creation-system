import { FormEvent, useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { api } from '../api/client';
import { ActionFailure, ActionSuccess, EmptyState, ErrorState, LoadingState } from '../components/Status';
import { useAsync } from '../features/useAsync';

export function GenresPage() {
  const { projectId = '' } = useParams();
  const genres = useAsync<Awaited<ReturnType<typeof api.listGenres>>>();
  const [fileName, setFileName] = useState('');
  const [feedback, setFeedback] = useState('');
  const [errorFeedback, setErrorFeedback] = useState('');

  useEffect(() => {
    void genres.run(() => api.listGenres());
  }, []);

  const onLoad = async (e: FormEvent) => {
    e.preventDefault();
    setFeedback('');
    setErrorFeedback('');
    try {
      const loaded = await api.loadGenre({ file_name: fileName });
      setFeedback(`题材档案已导入配置库：${loaded.genre_name}（${loaded.genre_id}）`);
      void genres.run(() => api.listGenres());
    } catch (err) {
      setErrorFeedback(err instanceof Error ? err.message : '导入失败');
    }
  };

  return (
    <div>
      <h2>题材配置库</h2>
      <p>当前项目上下文：{projectId || '-'}（仅用于导航上下文展示，不表示题材绑定变更）。</p>
      <div className="panel">本页用于查看可用题材与导入题材档案；项目级 genre_id 仍以项目创建时绑定为准。</div>

      <form onSubmit={onLoad} className="panel">
        <input value={fileName} onChange={(e) => setFileName(e.target.value)} placeholder="genre file_name" required />
        <button>导入题材档案</button>
      </form>
      {feedback && <ActionSuccess text={feedback} />} {errorFeedback && <ActionFailure text={errorFeedback} />}

      {genres.loading && <LoadingState />}
      {genres.error && <ErrorState text={genres.error} />}
      {genres.data?.length === 0 && <EmptyState text="题材配置库为空" />}
      <ul>
        {genres.data?.map((g) => (
          <li key={g.genre_id} className="panel">
            {g.genre_name} ({g.genre_id})
          </li>
        ))}
      </ul>
    </div>
  );
}
