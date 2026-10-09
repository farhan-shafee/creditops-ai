import { notFound } from 'next/navigation';
import { Console } from '@/components/console';
const views = [
  'live-operations',
  'incidents',
  'investigator',
  'observability',
  'service-map',
  'runbooks',
  'history',
  'evaluations',
  'architecture',
  'about',
];
export function generateStaticParams() {
  return views.map((view) => ({ view }));
}
export default async function Page({ params }: { params: Promise<{ view: string }> }) {
  const { view } = await params;
  if (!views.includes(view)) notFound();
  return <Console view={view} />;
}
