import { Bot, CheckCheck, Menu, Search, SendHorizontal, ChevronLeft } from "lucide-react";
import gradientBg  from "../../../assets/gradient.jpg"
import LiveTerminal from "@/features/streaming/components/LiveTerminal";
import { useSelectionStore } from "../../store/selectionStore";
import { useRepos } from "@/features/github/hooks/useRepos";
import { useStreamingSocket } from "@/features/streaming/hooks/useStreamingSocket";
import { useMemo, useState } from "react";
import { RepoCard } from "./ui/RepoCard";
import { SelectionToolbar } from "./SelectionToolbar";
import { WorkspaceDropdown } from "./ui/WorkspaceCard";
import { useAutonomicTokenRefresh } from "@/services/auth/useAutonomicTokenRefresh.ts"; 




export default function Dashboard() {
    useAutonomicTokenRefresh();
    const [isAiOpen, setIsAiOpen] = useState(false);
    const [isProcessingRequest, setIsProcessingRequest] = useState(false);
    const [isOn, setIsOn] = useState(false);
    const [prompt, setPrompt] = useState("");
    const { sendMessage } = useStreamingSocket();
    const [searchQuery, setSearchQuery] = useState('');
    const [selectedWorkspace, setSelectedWorkspace] = useState(""); // "" means "All Workspaces"

    const selected = useSelectionStore((state) => state.selected);
    console.log(selected, "selected repos in dashboard")
    
    const {
        data,
        isLoading,
        error,
    } = useRepos();
    console.log( "alagbara", data?.expires_at)
    localStorage.setItem("gh_token_expires_at", data?.expires_at);
     // Normalize data to avoid null errors
    // 🚀 DUAL-FILTER CONSOLIDATION ENGINE
    const filteredRepositories = useMemo(() => {
        if (!data?.repositories) return [];

        return data.repositories.filter((repo: any) => {
        // Filter Step A: Match Workspace selection boundaries
        if (selectedWorkspace && repo.workspaceName !== selectedWorkspace) {
            return false;
        }

        // Filter Step B: Match Search Input Query strings
        const cleanQuery = searchQuery.toLowerCase().trim();
        if (!cleanQuery) return true;
        
        return repo.full_name?.toLowerCase().includes(cleanQuery);
        });
    }, [data, searchQuery, selectedWorkspace]);

    console.log("filteredRepositories.length === 0 &&", filteredRepositories.length)
    // Active when there is a search query AND exactly one match is found
    const isSingleMatch = searchQuery.trim() !== '' && filteredRepositories.length === 1;

    const isAuthError = error && ((error as any).status === 401 || (error as any).status === 403);
    const serverDownError = (error && error instanceof TypeError && error.message === "Failed to fetch");
    // useMemo ensures this index is only recalculated if data actually changes.
    const selectedRepoIdsSet = useMemo(() => {
        if (!data || !data.repo_selection) return new Set();
        
        // Match the exact ID key property output by your serializer (e.g., 'id' or 'repo_id')
        return new Set(data.repo_selection.map(item => item.id || item.repo_id));
    }, [data]);


    if (isAuthError){
        console.log("Please log in with GitHub again to securely synchronize your workspace")
    }
    if (serverDownError){
        console.log("Server is down. Please try again later.")
    }
    console.log(error, "h1osana",data)

    function SolveSendIconTasks(){
        setIsProcessingRequest(true);
        setIsAiOpen(false);

        // sending message to the websocket
        sendMessage({
            type: "start_processing",
            repos: Array.from(selected),
            prompt,
        });
        // clearing the input prompt
        setPrompt("")
    }

    function ClickBackIconTasks(){
        if (isProcessingRequest) {
            setIsProcessingRequest(false);
            setIsAiOpen(true);
        }
        if (isAiOpen) {
            setIsAiOpen(false);
            setIsProcessingRequest(false);
        }
    }

    if (isLoading) {
        return <p className = "text-red-500 w-full h-full flex justify-center text-center">Loading...</p>;
    }

    if (error) {
        return <p className = "text-red-500 w-full h-full flex justify-center text-center">Error fetching repos</p>;
    }


    return (<div>

        <div className="w-full flex pr-4 pl-2">

        {/* left bar */}
        <div className=" xl:mr-0 w-[11.5%] h-full flex flex-col hidden md:block">

            <div className="tabs flex flex-col h-full">
                <div id="project-tabs" className="hidden xl:block">
                    <div
                        style={{ backgroundColor: '#be9ee2' }}
                        className="cursor-pointer w-full px-3 py-2 mt-[27px] rounded-lg  hover:bg-purple-200 hover:text-black flex items-center justify-start gap-3">
                        <CheckCheck className="cursor-pointer" />
                        <p >My Task</p>
                    </div>

                    <div
                        className="cursor-pointer w-full px-3 py-2  rounded-lg hover:bg-purple-200 hover:text-black flex items-center justify-start gap-3">
                        <i className="material-icons-outlined">group</i>
                        <p>Team</p>
                    </div>
                </div>

                {/* <!-- second tab  --> */}
                <div className="top-tabs w-full grid xl:hidden">
                    <p
                        className="cursor-pointer w-full px-3 py-2 mt-[27px] rounded-lg hover:bg-purple-200 bg-purple-300 hover:text-black flex items-center justify-start gap-3">
                        My Task</p>
                    <p
                        className="cursor-pointer w-full px-3 py-2  rounded-lg hover:bg-purple-200 hover:text-black flex items-center justify-start gap-3">
                        Team</p>
                    <p
                        className="cursor-pointer w-full px-3 py-2  rounded-lg hover:bg-purple-200 hover:text-black flex items-center justify-start gap-3">
                        File</p>
                    <p
                        className="cursor-pointer w-full px-3 py-2  rounded-lg hover:bg-purple-200 hover:text-black flex items-center justify-start gap-3">
                        Calendar</p>
                </div>

                {/* <!-- insights --> */}
                <div className="insights mt-8 ml-4 ">
                    <p className="mt-4 mb-4 text-black">Insights</p>
                </div>

            </div>
            
        </div>

        {/* center, topbar and right bar  */}
        <div className="w-[80%] left-right-container flex-grow">
            {/* topbar */}
            <div className="w-full pt-[10px]">
                <div className="w-full flex items-center gap-6 pl-2 pr-4">

                    {/*  my proj */}
                    <div className="my-proj w-fit hidden md:flex items-center gap-2">
                        <p className="font-bold text-black">Welcome, John</p>
                    </div>

                    {/* <!-- input box parent --> */}
                    <div className="flex justify-between items-center flex-grow">
                        {/* <!-- input box --> */}
                        <div className="w-[60%] xl:w-[72%] relative">
                            <input 
                                value={searchQuery}
                                onChange={(e) => setSearchQuery(e.target.value)}
                                id="input-search" 
                                type="text" 
                                placeholder="Search Repos & Workspace"
                                className="pl-4 rounded-xl h-[25px] w-full shadow-lg" />
                            <div id="search-icon" className="absolute top-[25%] right-3">
                                <Search className="w-4 h-4 text-gray-500" />
                            </div>

                        </div>

                        {/* <!-- chat support icon --> */}
                        <div onClick={() => {setIsAiOpen(!isAiOpen)}} id="ai-chat-support" className="md:w-[100px] w-fit p-4 mt-auto shadow-md rounded-full cursor-pointer grid items-center justify-center ">
                            <div className="w-full flex justify-center">
                                <Bot className="material-icons-outlined text-[12px]" />
                            </div>
                                <p className="text-[12px] hidden md:flex">Support</p>
                        </div>
                    </div>
                </div>
            </div>

            {/* parent of right nd center bar */}
            <div className="flex mt-4 h-[80vh]">
                {/* ceenter menu */}
                <div className="h-full w-[72%] flex-grow pr-4 pl-2">               
                    {/* repo menu */}                 
                    
                    {(!isAiOpen && !isProcessingRequest) && (<div className="px-10 py-3">
                        <SelectionToolbar switchOn = {setIsOn} isOn = {isOn} filteredRepos={filteredRepositories} />

                       {/* repo List */}
                        <div className="space-y-4">
                            {filteredRepositories.map((repo) => {
                            // It is "ticked" if all are shown (no single match) OR if it is the single match
                            const isActive = !isSingleMatch || filteredRepositories[0].id === repo.id;

                            return (
                                <RepoCard
                                    key={repo.id}
                                    id={String(repo.id)}
                                    name={repo.full_name}
                                    image={repo.avatar_url}
                                    isActive={isActive} // Pass the tick/active state to your card
                                    workspaceName={repo.workspaceName}
                                />
                            );
                            })}

                            {/* Fallback for empty results */}
                            {filteredRepositories.length === 0 && (
                            <p className="text-gray-500 text-sm flex justify-center mt-4">No Workspace or Repositories found.</p>
                            )}
                        </div>
                    </div>)}

                    {/* AI menu */}
                    {(isAiOpen || isProcessingRequest) && (<div className="AI-menu w-full h-full flex flex-col items-center justify-center gap-4">
                                                <div className="w-full md:w-[75%] px-3 py-4 h-full">
                            <div className="flex items-center justify-between">
                                <div className="md:hidden">
                                    <Menu id="expand-history" className="cursor-pointer"/>
                                </div>
                                <ChevronLeft onClick={() => ClickBackIconTasks()} className="cursor-pointer"/>
                            </div>
                            {/* ai-chat-placeholder */}
                            <div id="ai-chat-placeholder" className=" h-[100%] w-full justify-center items-center">
                            <p>Request status: {isAiOpen ? "aipageon..." : "Idle"}</p>
                                {/* chat panel */}
                                {(isAiOpen && !isProcessingRequest) && <div className="w-full h-[80%] flex flex-col items-center">
                                    <h1 className="text-black"><span id="gradient-text" className="bg-gradient-to-r from-[#be9ee2] to-white bg-clip-text text-transparent font-bold">Hy Dear</span> This is an AI assited chat</h1>
                                    <img src={gradientBg } alt="Robot AI" className="w-[35%]" style={{ width : "35%"}} />
                                    <p className="text-black pt-3">How can i help?</p>
                                    {/* input */}
                                    <div className="w-[70%] h-[20%] justify-self-center">
                                        <div className="relative w-[90%] h-[60%]">
                                            <input
                                                value={prompt}
                                                onChange={(e) =>
                                                    {
                                                        setPrompt(e.target.value);
                                                        console.log(prompt)

                                                    }                                              
                                                } 
                                                id="ai-chat" type="text" placeholder="Chat"
                                                className={`pl-4 rounded-xl border w-full h-full ${isProcessingRequest ? "hidden" : ""}`} style={{borderColor: "black"}} />
                                            <div onClick={() => 
                                                SolveSendIconTasks()
                                                }
                                                id="send-icon" className="absolute top-[30%] right-[5%] cursor-pointer">
                                                <SendHorizontal/>            
                                            </div>
                                        </div>
                                    </div>
                                </div>}

                                {/* live terminal component */}
                                {(isProcessingRequest && !isAiOpen) && (
                                    <div className="w-full h-[80%]">
                                        <LiveTerminal />
                                    </div>
                                )}

                            </div>
                            
                        </div>
                    </div>)}
                </div>

                {/* right bar */}
                <div className="w-[25%] h-full pt-3 items-end pl-4 hidden lg:flex flex-col">
                    
                    {/* Search Input Field */}
                    <div className="space-y-4">
                        {/* workspace List */}
                        <div className="space-y-4">
                            <WorkspaceDropdown
                                workspaces={data?.uniqueWorkspaces || []}
                                selectedWorkspace={selectedWorkspace}
                                onSelectWorkspace={setSelectedWorkspace}
                            />
                        </div>
                    </div>

                    <button
                    >
                        create repo
                    </button>

                </div>  
    </div>
        </div>
            </div>
        </div>);
        
}