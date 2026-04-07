export function LoadingState({ text = '加载中...' }: { text?: string }) {
  return <div className="state loading">{text}</div>;
}

export function EmptyState({ text = '暂无数据' }: { text?: string }) {
  return <div className="state empty">{text}</div>;
}

export function ErrorState({ text }: { text: string }) {
  return <div className="state error">请求失败：{text}</div>;
}

export function BlockedState({ text }: { text: string }) {
  return <div className="state blocked">阻断：{text}</div>;
}

export function PendingApprovalState({ text = '存在待审批事项' }: { text?: string }) {
  return <div className="state pending">{text}</div>;
}

export function ActionSuccess({ text }: { text: string }) {
  return <div className="state success">✅ {text}</div>;
}

export function ActionFailure({ text }: { text: string }) {
  return <div className="state action-fail">❌ {text}</div>;
}
