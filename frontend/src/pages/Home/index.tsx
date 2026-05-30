import { Chat } from "@/features/streaming/components/Chat";
import  Dashboard  from "@/features/dashboard/components/Dashboard";

export default function Home() {
  return <div>
    <Dashboard /> 
    <Chat />
    </div>;
}
