import { useMemo, useState } from "react";
import { Bot, CheckCheck, Menu, Search, SendHorizontal, ChevronLeft, Plus } from "lucide-react";
import { toast } from 'react-toastify';
import gradientBg  from "../../../assets/gradient.jpg"
import LiveTerminal from "@/features/streaming/components/LiveTerminal";
import { useSelectionStore } from "../../store/selectionStore";
import { useLLMStore } from "../../store/selectionStore";
import { useSocketStore  } from "../../store/selectionStore";
import { items } from "../../data/dummyData";
import { useRepos } from "@/features/github/hooks/useRepos";
import { useStreamingSocket } from "@/features/streaming/hooks/useStreamingSocket";
import { RepoCard } from "./ui/RepoCard";
import { SelectionToolbar } from "./SelectionToolbar";
import { WorkspaceDropdown } from "./ui/WorkspaceCard";
import { WorkspaceModal } from "./ui/CreateWorkspaceModal";
import { useCreateReposMutation, useCreateEnvKeysMutation } from "@/features/odozi/hooks/useRepoMutations";
import { useAutonomicTokenRefresh } from "@/services/auth/useAutonomicTokenRefresh";
import { EnvVarModal } from "./ui/ENV vars/EnvVarModal"; 
import { LLMConfigModal } from "./ui/ENV vars/LLMConfigModal";
import TestRepoEndpoint from "./ui/TestRepoEndpoint";
// import {AgenticChatConsole} from "@features/streaming/api/AiChat.tsx"
// import { EnvVariableCard } from "./ui/ENV vars/EnvVariableCard";




export default function Dashboard() {
    const backendUrl = import.meta.env.VITE_DJANGO_BACKEND_URL || 'http://127.0.0.1:8000';
    useAutonomicTokenRefresh();
    const [isAiOpen, setIsAiOpen] = useState(false);
    const [isPending, setIsPending] = useState(false);
    const [isProcessingRequest, setIsProcessingRequest] = useState(false);
    const [isOn, setIsOn] = useState(false);
    const [envShowModal, setEnvShowModal] = useState(false);
    const [showLlmModal, setShowLlmModal] = useState(false);
    const [prompt, setPrompt] = useState("");
    const { sendMessage } = useStreamingSocket();
    const [searchQuery, setSearchQuery] = useState('');
    const [selectedWorkspace, setSelectedWorkspace] = useState(""); // "" means "All Workspaces"

    const selected = useSelectionStore((state) => state.selected);
    const useCreateRepos = useCreateReposMutation();
    const useCreateEnv = useCreateEnvKeysMutation();
    const [isModalOpen, setIsModalOpen] = useState(false)
    console.log(selected, "selected repos in dashboard")
    
    const {
        data,
        isLoading,
        error,
    } = useRepos();
    console.log( "alagbara", data?.expires_at)
    localStorage.setItem("gh_token_expires_at", data?.expires_at);
    const get_time_obj = localStorage.getItem("jwt_token_expires_at");
    if (!get_time_obj && !get_time_obj["token"]) {
        const manualExpiryTimeMs = Date.now() + 90000;
        localStorage.setItem("jwt_token_expires_at", JSON.stringify({ token: String(manualExpiryTimeMs), dont_touch: true }));
        console.log("ran_tokennnnn")
    } else {
        console.log("Existing JWT expiry timestamp found in localStorage:", get_time_obj);
    }
    console.log("🔒 Tokens captured in RAM. Timestamp cached to localStorage.", localStorage.getItem("gh_token_expires_at"));

     // Normalizing data to avoid null errors
    const filteredRepositories = useMemo(() => {
        if (!data?.repositories) return [];

        return items.filter((repo: any) => {
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

    
      // Zustand Store variables
    const selectedIdsSet = useSelectionStore((state) => state.selected);
    const toggleSelect = useSelectionStore((state) => state.toggleSelect);
    const clearSelection = useSelectionStore((state) => state.clearSelection);
    
    const { activeProvider, activeModel, savedApiKey } = useLLMStore();
    const activeToast = useSocketStore((state) => state.activeToast);
    const clearActiveToast = useSocketStore((state) => state.clearActiveToast);

   


    const handleCreateWorkspace = (modalPayload: { workspaceName: string }) => {
        console.log("manage")
        // if (selectedIdsSet.size === 0 || !data?.repositories) return;
        console.log("baby")

        // Filter our cached collection matching the active Zustand Set configurations
        const serializedRepos = items
            .filter((repo: any) => selectedIdsSet.has(String(repo.id)))
            .map((repo: any) => {
            const nameParts = repo.full_name.split("/");
            return {
                repo_id: Number(repo.id),
                repo_name: nameParts[1] || repo.name,
                repo_owner: nameParts[0] || "Unknown",
                repo_full_name: repo.full_name
            };
            });

        useCreateRepos.mutate({
            workspaceId: null, // Signals backend view path B to trigger a brand-new workspace insert
            newWorkspaceName: modalPayload.workspaceName,
            repositories: serializedRepos
        }, {
            onSuccess: () => {
            clearSelection();
            setIsModalOpen(false);
            toast.success("Workspace created with selected repositories!", {
                position: "top-right",
                autoClose: 2000,
                theme: "dark",
                style: {
                    background: "linear-gradient(to right, #00b09b, #96c93d)",
                    color: "#fff"          
                }
                });
            
            },
            onError: (err: any) => {
                toast(`❌ Error compiling pipelines: ${err.message}`, {
                    autoClose: 3000,         // Closes after 3 seconds
                    position: "top-right",   // Combines your gravity ("top") and position ("right")
                    pauseOnFocusLoss: true,  // Equivalent to stopOnFocus: true
                    
                    // Custom styling to inject your linear gradient background
                    style: {
                        background: "linear-gradient(to right, #00b09b, #96c93d)",
                        color: "#fff"          // Ensures your text is readable over the gradient
                    }
                    });
            }
        });
    };


const createEnvVar = (keyList: string[], workspace:string) => {
  // Use 'items' or 'allRepositories' depending on your state name
  const serializedRepos = items
    .filter((repo: any) => selectedIdsSet.has(String(repo.id)))
    .map((repo: any) => {
      const nameParts = repo.full_name.split("/");
      return {
        repo_id: Number(repo.id),
        repo_name: nameParts[1] || repo.name,
        repo_owner: nameParts[0] || "Unknown",
        repo_full_name: repo.full_name
      };
    });

    console.log("eze yo yo",{
    workspace: workspace, 
    repositories: serializedRepos,
    key_names: keyList,
    selected:selected 
  })
  // Fire everything to your dynamic Django view!
  useCreateEnv.mutate({
    workspace: workspace, 
    repositories: serializedRepos,
    key_names: keyList,
    selected:Array.from(selected) 
  }, {
    onSuccess: () => {
    //   clearSelection();
      setEnvShowModal(false);
    },
  });
};


 const handleSendRequest = async (e: React.FormEvent) => {
    e.preventDefault();
     console.log(activeToast !== null,"activetoast", activeToast)
        if (activeToast !== null){
                toast.error(activeToast.message || "Gateway terminated connection: Reconnecting", {
                position: "top-right",
                autoClose: 4000,
                theme: "colored"
            });

            return
        }
    const cleanedInput = prompt.trim();
    if (!cleanedInput) return;

    setIsPending(true);
    setIsProcessingRequest(true);
    setIsAiOpen(false);
    console.log(activeModel,"buzz",activeProvider, "77", savedApiKey)

    sendMessage({
        type: "start_processing",
        prompt: cleanedInput,
        provider: activeProvider,
        model_name: activeModel,
        user_api_key: savedApiKey // Securely forward their credential keys
    });


    setIsPending(false);
  };


    console.log(selected,"filteredRep", selectedWorkspace)
    // Active when there is a search query AND exactly one match is found
    const isSingleMatch = searchQuery.trim() !== '' && filteredRepositories.length === 1;

    const isAuthError = error && ((error as any).status === 401 || (error as any).status === 403);
    const serverDownError = (error && error instanceof TypeError && error.message === "Failed to fetch");


    // if (isAuthError){
    //     console.log("Please log in with GitHub again to securely synchronize your workspace")
    // }
    // if (serverDownError){
    //     console.log("Server is down. Please try again later.")
    // }
    console.log(error, "h1osana",data)

    function SolveSendIconTasks(){
        

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

    // if (isLoading) {
    //     return <p className = "text-red-500 w-full h-full flex justify-center text-center">Loading...</p>;
    // }

    // if (error) {
    //     return <p className = "text-red-500 w-full h-full flex justify-center text-center">Error fetching repos</p>;
    // }


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
                        History</p>
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
                            {items.map((repo) => {
                            // It is "ticked" if all are shown (no single match) OR if it is the single match
                            const isActive = !isSingleMatch || filteredRepositories[0].id === repo.id;

                            return (
                                <RepoCard
                                    key={repo.id}
                                    id={String(repo.id)}
                                    name={repo.full_name}
                                    image={"repo.avatar_url"}
                                    isActive={isActive} // Pass the tick/active state to your card
                                    workspaceName={"repo.workspaceName"}
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
                                                {isPending ? (

                                                    <form onSubmit={handleSendRequest} className="relative w-full">
                                                        <input 
                                                        type="text"
                                                        value={prompt}
                                                        onChange={(e) => setPrompt(e.target.value)}
                                                        placeholder="Type a message..."
                                                        className={`pl-4 rounded-xl border w-full h-full ${isProcessingRequest ? "hidden" : ""}`} style={{borderColor: "black"}}
                                                        />
                                                        
                                                        <button 
                                                        type="submit" 
                                                        id="send-icon" 
                                                        className="animate-spin absolute top-[30%] right-[5%] cursor-pointer"
                                                        disabled={isPending || !prompt.trim()}
                                                        >
                                                        <SendHorizontal />            
                                                        </button>
                                                    </form>
                                                    
                                                ) : (
                                                    <form onSubmit={handleSendRequest} className="relative w-full">
                                                        <input 
                                                        type="text"
                                                        value={prompt}
                                                        onChange={(e) => setPrompt(e.target.value)}
                                                        placeholder="Type a message..."
                                                        />
                                                        
                                                        {/* 🌟 Icon turned into a submit button. NO onClick handler needed! */}
                                                        <button 
                                                        type="submit" 
                                                        id="send-icon" 
                                                        className="absolute top-[30%] right-[5%] cursor-pointer bg-transparent border-none p-0"
                                                        >
                                                        <SendHorizontal />            
                                                        </button>
                                                    </form>
                                                )}
                                            
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
                <div className="w-[25%] h-full pt-3 items-center gap-4 pl-4 hidden lg:flex flex-col justify-start">

                    {/* Include your absolute rendering portal layer down at the bottom of the node string tree */}
                    <WorkspaceModal
                        isOpen={isModalOpen}
                        onClose={() => setIsModalOpen(false)}
                        allRepositories={items || []} // ✅ Feed the entire collection into the modal!
                        selectedIds={selectedIdsSet}               // ✅ Pass the store selection tracker reference
                        onToggleSelect={toggleSelect}               // ✅ Pass the action selection click modifier handler
                        onSubmit={handleCreateWorkspace}
                        isPending={useCreateRepos.isPending}
                    />
                    
                    <div className="w-full space-y-4 flex items-center">
                        <button 
                            onClick={() => setIsModalOpen(true)}
                            className="p-1 mt-2 bg-green-500 hover:bg-green-700 text-white rounded-full shadow-sm transition-colors cursor-pointer mr-4"
                            >
                            <Plus className="w-5 h-5" />
                        </button>
                        {/* workspace List */}
                        <div className="space-y-4">
                            <WorkspaceDropdown
                                workspaces={data?.uniqueWorkspaces || ["olive corp"]}
                                selectedWorkspace={selectedWorkspace}
                                onSelectWorkspace={setSelectedWorkspace}
                            />
                        </div>
                    </div>
                    {/* create env variables */}
                    <div className="flex items-center gap-2 px-4 py-2.5 bg-white border border-gray-300 rounded-xl cursor-pointer hover:bg-gray-50 transition-colors shadow-sm select-none"
                        onClick={() => setEnvShowModal(!envShowModal)}
                    >
                        <span className="text-sm font-semibold text-gray-700">
                        Create env vars
                        </span>
                    </div>
                    {envShowModal &&<EnvVarModal 
                    isOpen={envShowModal} 
                    onClose={() => setEnvShowModal(false)} 
                    selected={selected}
                    workspace = {selectedWorkspace} 
                    onSubmit={createEnvVar}
                    isPending={useCreateEnv.isPending}
                    
                    />} 
                    {/* select LLM */}
                    <div className="flex items-center gap-2 px-4 py-2.5 bg-white border border-gray-300 rounded-xl cursor-pointer hover:bg-gray-50 transition-colors shadow-sm select-none"
                        onClick={() => setShowLlmModal(!showLlmModal)}
                    >
                        <span className="text-sm font-semibold text-gray-700">
                        Select LLM
                        </span>
                    </div> 
                    {showLlmModal &&<LLMConfigModal isOpen={showLlmModal} onClose={() => setShowLlmModal(false)}/> }

                    <TestRepoEndpoint />

                </div>  
    </div>
        </div>
            </div>
        </div>);
        
}