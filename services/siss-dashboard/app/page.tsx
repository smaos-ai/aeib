import { prisma } from '@/lib/prisma';
import Link from 'next/link';

export default async function Dashboard() {
  const repositories = await prisma.codeRepository.findMany({
    include: { _count: { select: { document: true } } },
    orderBy: { createdAt: 'desc' }
  });

  return (
    <main className="min-h-screen bg-gray-950 text-gray-100 p-8">
      <div className="max-w-6xl mx-auto">
        <header className="mb-8 border-b border-gray-800 pb-4">
          <h1 className="text-3xl font-bold tracking-tight text-white">SMAOS Knowledge Dashboard</h1>
          <p className="text-gray-400 mt-2">Monitoring {repositories.length} ingested repositories in the local RAG pipeline.</p>
        </header>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {repositories.map((repo) => (
            <Link href={`/repository/${repo.id}`} key={repo.id} className="bg-gray-900 border border-gray-800 rounded-xl p-6 shadow-sm hover:border-blue-500 transition-colors block">
              <div className="flex justify-between items-start mb-4">
                <h2 className="text-xl font-semibold text-blue-400 truncate">{repo.name}</h2>
                <span className="bg-gray-800 text-xs px-2 py-1 rounded text-gray-300">{repo.language || 'Mixed'}</span>
              </div>
              <div className="space-y-2 text-sm text-gray-400">
                <p><strong className="text-gray-300">Indexed Files:</strong> {repo._count.document}</p>
                <p><strong className="text-gray-300">Ingested:</strong> {new Date(repo.createdAt).toLocaleDateString()}</p>
              </div>
            </Link>
          ))}
        </div>
      </div>
    </main>
  );
}
