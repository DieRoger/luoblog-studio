import { Activity, BookOpen, FileText, Search } from "lucide-react";

export default function HomePage() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center px-4">
      <div className="max-w-2xl text-center space-y-6">
        <h1 className="text-4xl font-bold tracking-tight">LuoBlog Studio</h1>
        <p className="text-lg text-gray-600">
          Personal AI Engineering Knowledge OS — transform engineering experience
          into structured knowledge and technical publications.
        </p>

        <div className="grid grid-cols-2 gap-4 mt-8 text-left">
          <FeatureCard icon={Search} title="Knowledge Hub" desc="Import, parse, and search your technical documents" />
          <FeatureCard icon={BookOpen} title="Research Engine" desc="AI-powered research across papers and code" />
          <FeatureCard icon={FileText} title="Writing Agent" desc="Generate evidence-backed blog drafts" />
          <FeatureCard icon={Activity} title="Evidence Layer" desc="Every claim backed by a source" />
        </div>

        <p className="text-sm text-gray-400 mt-8">Phase 0 — Infrastructure Initialized</p>
      </div>
    </main>
  );
}

function FeatureCard({ icon: Icon, title, desc }: { icon: React.ComponentType<{ className?: string }>; title: string; desc: string }) {
  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4">
      <Icon className="w-5 h-5 text-[#7C3AED] mb-2" />
      <h3 className="font-medium text-sm">{title}</h3>
      <p className="text-xs text-gray-500 mt-1">{desc}</p>
    </div>
  );
}
