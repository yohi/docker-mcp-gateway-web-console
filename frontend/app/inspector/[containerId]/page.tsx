import { notFound } from 'next/navigation';
import InspectorPageClient from '@/app/inspector/[containerId]/InspectorPageClient';
import {
  InspectorParamsInput,
  InspectorSearchParamsInput,
  resolveInspectorRouteParams,
} from '@/app/inspector/[containerId]/routeParams';

type InspectorPageProps = {
  params: Promise<{ containerId?: string | string[] }>;
  searchParams?: Promise<{ [key: string]: string | string[] | undefined }>;
};

export default async function InspectorPage({
  params,
  searchParams,
}: InspectorPageProps) {
  const { containerId, containerName } = await resolveInspectorRouteParams(params, searchParams);

  if (!containerId) {
    notFound();
  }

  return <InspectorPageClient containerId={containerId} containerName={containerName} />;
}
