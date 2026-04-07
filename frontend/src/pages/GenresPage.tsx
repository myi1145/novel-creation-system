import { FormEvent, useEffect, useState } from 'react';
import { api } from '../api/client';
import { ActionFailure, ActionSuccess, EmptyState, ErrorState, LoadingState } from '../components/Status';
import { useAsync } from '../features/useAsync';

export function GenresPage() {
  const genres = useAsync<Awaited<ReturnType<typeof api.listGenres>>>();
  const [fileName, setFileName] = useState('');
  const [feedback, setFeedback] = useState('');
  const [errorFeedback, setErrorFeedback] = useState('');

  useEffect(() => {
    void genres.run(() => api.listGenres());
  }, []);

  const onImport = async (e: FormEvent) => {
    e.preventDefault();
    setFeedback('');
    setErrorFeedback('');
    try {
      const loaded = await api.loadGenre({ file_name: fileName });
      setFeedback(`题材档案已导入：${loaded.genre_name}`);
      await genres.run(() => api.listGenres());
    } catch (err) {
      setErrorFeedback(err instanceof Error ? err.message : '导入失败');
    }
  };

  return (
    <div>
      <h2>题材档案导入 / 可用题材查看</h2>
      <p className="panel">说明：本页仅处理题材档案导入与可用题材列表，不做项目级题材绑定。</p>
      <form onSubmit={onImport} className="panel">
        <input value={fileName} onChange={(e) => setFileName(e.target.value)} placeholder="genre file_name" required />
        <button>导入题材档案</button>
      </form>
      {feedback && <ActionSuccess text={feedback} />}
      {errorFeedback && <ActionFailure text={errorFeedback} />}
      {genres.loading && <LoadingState />}
      {genres.error && <ErrorState text={genres.error} />}
      {genres.data?.length === 0 && <EmptyState text="当前没有可用题材" />}
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
