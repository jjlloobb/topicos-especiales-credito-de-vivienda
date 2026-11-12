export const Unsafe = ({ html }: { html: string }) => <div dangerouslySetInnerHTML={{ __html: html }} />;
