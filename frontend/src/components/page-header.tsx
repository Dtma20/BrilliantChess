export function PageHeader({
  title,
  lede,
  children,
}: {
  title: string
  lede?: React.ReactNode
  children?: React.ReactNode
}) {
  return (
    <div className="mb-4">
      <h1 className="m-0 text-[1.4rem] leading-tight font-medium">{title}</h1>
      {lede && <p className="mt-1.5 mb-0 max-w-[62ch] text-[0.9rem] text-ink-3">{lede}</p>}
      {children}
    </div>
  )
}
