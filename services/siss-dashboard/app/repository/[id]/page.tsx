import { prisma } from '@/lib/prisma';
import Link from 'next/link';

interface RepositoryDetailsProps {
  params: Promise<{ id: string }>;
}

export default async function RepositoryDetails({ params }: RepositoryDetailsProps) {
  const { id } = await params;

  const repo = await prisma.codeRepository.findUnique({
    where: { id },
    include: {
      document: {
        orderBy: { path: 'asc' },
        include: {
          _count: { select: { chunk: true } },
          chunk: {
            orderBy: { chunkIndex: 'asc' },
          }
        }
      }
    }
  });

  if (!repo) return <div className="p-8 text-white">Repository not found.</div>;

  return (
    <main className="min-h-screen bg-gray-950 text-gray-100 p-8">
      <div className="max-w-6xl mx-auto">
        <header className="mb-8 border-b border-gray-800 pb-4">
          <Link href="/" className="text-blue-500 hover:underline text-sm mb-4 inline-block">&larr; Back to Dashboard</Link>
          <h1 className="text-3xl font-bold text-white">{repo.name}</h1>
          <p className="text-gray-400 mt-1">Source: {repo.url}</p>
        </header>

        <div className="space-y-8">
          <h2 className="text-2xl font-semibold text-gray-200">Indexed Documents & Chunks</h2>
          {repo.document.map((doc) => (
            <div key={doc.id} className="bg-gray-900 border border-gray-800 rounded-xl p-6">
              <div className="flex justify-between items-center mb-4 border-b border-gray-800 pb-4">
                <h3 className="text-lg font-mono text-blue-400">{doc.path}</h3>
                <span className="bg-gray-800 text-xs px-3 py-1 rounded text-gray-300">
                  {doc.type} | {doc.language} | {doc._count.chunk} Chunks
                </span>
              </div>

              <div className="space-y-4">
                {doc.chunk.map((c) => (
                  <div key={c.id} className="bg-black border border-gray-800 rounded-md p-4">
                    <div className="flex justify-between text-xs text-gray-500 mb-2 font-mono">
                      <span>Chunk #{c.chunkIndex}</span>
                      <span>Estimated Tokens: {c.tokenCount}</span>
                    </div>
                    <pre className="text-sm text-gray-300 overflow-x-auto whitespace-pre-wrap max-h-64">
                      {c.content}
                    </pre>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </main>
  );
}
