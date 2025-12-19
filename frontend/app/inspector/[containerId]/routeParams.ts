export type InspectorParamsInput =
  | { containerId?: string | string[] }
  | Promise<{ containerId?: string | string[] } | undefined>
  | undefined;

export type InspectorSearchParamsInput =
  | URLSearchParams
  | { [key: string]: string | string[] | undefined }
  | Promise<URLSearchParams | { [key: string]: string | string[] | undefined } | undefined>
  | undefined;

export type ResolvedInspectorParams = {
  containerId: string | undefined;
  containerName?: string;
};

export async function resolveInspectorRouteParams(
  paramsInput: InspectorParamsInput,
  searchParamsInput: InspectorSearchParamsInput
): Promise<ResolvedInspectorParams> {
  const params = await paramsInput;
  const searchParams = await searchParamsInput;

  const extractFirst = (value?: string | string[] | null): string | undefined => {
    if (!value) return undefined;
    return Array.isArray(value) ? value[0] : value;
  };

  const containerId = extractFirst(params?.containerId);

  let containerName: string | undefined;
  if (searchParams instanceof URLSearchParams) {
    containerName = searchParams.get('name') ?? undefined;
  } else if (searchParams) {
    containerName = extractFirst(searchParams.name);
  }

  return {
    containerId,
    containerName,
  };
}
