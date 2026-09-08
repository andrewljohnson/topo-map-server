/** Resolve the API origin without URL-encoding MapLibre's tile placeholders. */
export function tileTemplateUrl(path: string, api: string): string {
  return new URL(path, api).href.replace(/%7B(z|x|y)%7D/gi, '{$1}');
}
