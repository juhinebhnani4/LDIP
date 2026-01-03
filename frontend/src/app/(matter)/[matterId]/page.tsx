interface MatterPageProps {
  params: Promise<{ matterId: string }>;
}

export default async function MatterPage({ params }: MatterPageProps) {
  const { matterId } = await params;

  return (
    <div className="space-y-6 p-6">
      <h1 className="text-3xl font-bold">Matter Workspace</h1>
      <p className="text-muted-foreground">Matter ID: {matterId}</p>
      {/* Tab bar and content area will be implemented in Epic 10A */}
    </div>
  );
}
