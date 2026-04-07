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

  useEffect(() => { void genres.run(() => api.listGenres()); }, []);

  const onLoad = async (e: FormEvent) => {
    e.preventDefault();
    setFeedback(''); setErrorFeedback('');
    try {
      const loaded = await api.loadGenre({ file_name: fileName });
      setFeedback(`项目 ${projectId} 已装载题材：${loaded.genre_name}`);
    } catch (err) { setErrorFeedback(err instanceof Error ? err.message : '装载失败'); }
  };

  return <div><h2>题材装载</h2>
    <form onSubmit={onLoad} className="panel"><input value={fileName} onChange={(e)=>setFileName(e.target.value)} placeholder="genre file_name" required/><button>装载题材</button></form>
    {feedback && <ActionSuccess text={feedback} />} {errorFeedback && <ActionFailure text={errorFeedback} />}
    {genres.loading && <LoadingState />} {genres.error && <ErrorState text={genres.error} />}
    {genres.data?.length===0 && <EmptyState text="无可用题材"/>}
    <ul>{genres.data?.map((g)=><li key={g.genre_id} className="panel">{g.genre_name} ({g.genre_id})</li>)}</ul>
  </div>;
}
