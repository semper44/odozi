import { useMemo, useState, useEffect } from "react";
import { Bot,House, CheckCheck, Menu, Search, SendHorizontal, ChevronLeft, ChevronDown, Plus } from "lucide-react";
import { toast } from 'react-toastify';
import gradientBg  from "../../../assets/gradient.jpg"
import LiveTerminal from "@/features/streaming/components/LiveTerminal";
import {AIChat, type ChatMessage } from "@/features/streaming/components/ChatMessage";
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
import { GitHubInstallation } from "../../../pages/registrationorlogin/install_github";
// import {AgenticChatConsole} from "@features/streaming/api/AiChat.tsx"
// import { EnvVariableCard } from "./ui/ENV vars/EnvVariableCard";




export default function Dashboard() {
    const backendUrl = import.meta.env.VITE_DJANGO_BACKEND_URL || 'http://127.0.0.1:8000';
    useAutonomicTokenRefresh();
    const [isAiOpen, setIsAiChatOpen] = useState(false);
    const [isPending, setIsPending] = useState(false);
    const [isProcessingRequest, setIsProcessingRequest] = useState(false);
    const [isOn, setIsOn] = useState(false);
    const [envShowModal, setEnvShowModal] = useState(false);
    const [showLlmModal, setShowLlmModal] = useState(false);
    const [prompt, setPrompt] = useState("");
    const [messages, setMessages] = useState<ChatMessage[]>([]);
    const [searchQuery, setSearchQuery] = useState('');
    const [selectedWorkspace, setSelectedWorkspace] = useState(""); // "" means "All Workspaces"
    const [isModalOpen, setIsModalOpen] = useState(false)
    const [showInstallModal, setShowInstallModal] = useState(true);

    const [activeLeftTab, setActiveLeftTab] = useState("Home");
    const [isHistoryOpen, setIsHistoryOpen] = useState(false);
    const historyItems = ["Repository setup", "Environment variables", "Deploy checklist"];
    const leftTabs = [
        { id: "Home", label: "Home", icon: <House className="cursor-pointer" /> },
        { id: "Chat", label: "Chat", icon: <Bot className="cursor-pointer" /> },
        { id: "History", label: "History", icon: <CheckCheck className="cursor-pointer" /> },
    ];

    const selected = useSelectionStore((state) => state.selected);
    const useCreateRepos = useCreateReposMutation();
    const useCreateEnv = useCreateEnvKeysMutation();
    const socketError = useSocketStore((state) => state.socketError);
    const streamingMessage = useSocketStore((state) => state.streamingMessage);  // ✅ Access from store
    const isProcessing = useSocketStore((state) => state.isProcessing);
    // const statusMessage = useSocketStore((state) => state.statusMessage);
    const { sendMessage } = useStreamingSocket((packet) => {
        console.log(socketError, "🎯 Caught incoming orchestration block payload:", packet);
        
        if (packet.raw_output.chat_response) {
            // Create and append the AI reply text frame
            const newAiMessage: ChatMessage = {
                id: crypto.randomUUID(),
                sender: "ai",
                text: packet.raw_output.chat_response,
            };
            
            setMessages((prev) => [...prev, newAiMessage]);
        }
    });

    useEffect(() => {
        if (socketError) {
            console.log("🚨 Dashboard caught background worker crash or API block:", socketError);
            
            // Append a system or error message to your chat interface display window
            if (socketError.isImportant) {
                const errorSystemMessage: ChatMessage = {
                    id: crypto.randomUUID(),
                    sender: "ai", // or "system" depending on your layout style
                    text: socketError.message || "An unexpected error occurred. Please try again.", 
                };
            
            setMessages((prev) => [...prev, errorSystemMessage]);
            } 
        }
    }, [socketError]);

    console.log(selected, "selected repos in dashboard")
    
    const {
        data,
        isLoading,
        error,
    } = useRepos();

    // useEffect(() => {
    //     if (isLoading) return;

    //     if (data?.installGithub === true) {
    //         setShowInstallModal(true);
    //         setHasCheckedInstallPrompt(true);
    //         return;
    //     }

    //     if (data?.installGithub === false) {
    //         setHasCheckedInstallPrompt(true);
    //     }
    // }, [data?.installGithub, hasCheckedInstallPrompt, isLoading]);

    
    // ✅ Console log streaming messages in Dashboard
    useEffect(() => {
        if (streamingMessage) {
            console.log("🎯 Dashboard caught streaming packet:", streamingMessage);
        }
    }, [streamingMessage]);

    console.log( "alagbara", error)
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
    
    const { activeProvider, activeModel } = useLLMStore();
    console.log("could",activeProvider, activeModel)
    const activeToast = useSocketStore((state) => state.activeToast);

   

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
};


 const handleSendRequest = async (textInput: string) => {
     console.log(activeToast !== null,"activetoast", activeToast)
     console.log({"yyyyyyyyyyy":activeProvider, "activeModel":activeModel})
     if(activeProvider === '' || activeModel === ''){
         toast.error("Please fill in the LLM details first", {
             position: "top-right",
                autoClose: 4000,
                theme: "colored"
            });

            return
        }  
    if (activeToast !== null){
            alert(9999999)
            toast.error(activeToast.message || "Gateway terminated connection: Reconnecting", {
            position: "top-right",
            autoClose: 4000,
            theme: "colored"
        });

        return
    }

    // alert(`${prompt}---${!textInput}-${textInput}`)

    const cleanedInput = textInput.trim();
    if(!cleanedInput){
        alert("none")
        return
    }

    // alert(textInput) 

    useSocketStore.getState().setProcessingStatus(true, "AI is spinning up orchestration jobs...");


    setIsPending(true);
    setIsProcessingRequest(true);
    setIsAiChatOpen(true);
    console.log(activeModel,"buzz",activeProvider, "77")

    // Append user bubble instantly to the UI tree layout
    const newUserMessage: ChatMessage = {
      id: crypto.randomUUID(),
      sender: "user",
      text: cleanedInput,
    };
    setMessages((prev) => [...prev, newUserMessage]);

    sendMessage({
        type: "start_processing",
        prompt: cleanedInput,
        provider: activeProvider,
        model_name: activeModel,
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


    function ClickBackIconTasks(){
        if (isProcessingRequest) {
            setIsProcessingRequest(false);
            setIsAiChatOpen(true);
        }
        if (isAiOpen) {
            setIsAiChatOpen(false);
            setIsProcessingRequest(false);
        }
    }

    const handleLeftTabClick = (tabId: string) => {
        setActiveLeftTab(tabId);

        if (tabId === "Chat") {
            setIsAiChatOpen((isOpen) => !isOpen);
        }

        if (tabId === "History") {
            setIsHistoryOpen((isOpen) => !isOpen);
        }
    };

    // if (isLoading) {
    //     return <p className = "text-red-500 w-full h-full flex justify-center text-center">Loading...</p>;
    // }

    // if (error) {
    //     return <p className = "text-red-500 w-full h-full flex justify-center text-center">Error fetching repos</p>;
    // }


    return (
        <>
        <div className="w-full flex pr-4 pl-2">

            {/* left bar */}
            <div className=" xl:mr-0 w-[11.5%] h-full flex flex-col hidden md:block pt-3">

                <div className="tabs flex flex-col h-full">
                    <div id="project-tabs" className="w-full hidden xl:grid top-tabs gap-2">
                        {leftTabs.map((tab) => {
                            const isActive = activeLeftTab === tab.id;
                            return (
                                <div key={tab.id}>
                                    <div
                                        onClick={() => handleLeftTabClick(tab.id)}
                                        className={`cursor-pointer w-full px-3 py-2 rounded-lg flex items-center justify-start gap-3 transition-colors ${isActive ? "bg-purple-300 text-black" : "bg-transparent hover:bg-purple-200 hover:text-black"}`}>
                                        {tab.icon}
                                        <p>{tab.label}</p>
                                        {tab.id === "History" && (
                                            <ChevronDown className={`ml-auto h-4 w-4 transition-transform duration-200 ${isHistoryOpen ? "rotate-180" : ""}`} />
                                        )}
                                    </div>
                                    {tab.id === "History" && isHistoryOpen && (
                                        <div className="mt-3 ml-9 space-y-2 border-l border-purple-200 pl-3">
                                            {historyItems.map((item) => (
                                                <button
                                                    key={item}
                                                    type="button"
                                                    className="block w-full text-left text-xs text-gray-600 hover:text-purple-700"
                                                >
                                                    {item}
                                                </button>
                                            ))}
                                        </div>
                                    )}
                                </div>
                            );
                        })}
                    </div>

                    {/* <!-- second tab  --> */}
                    <div className="top-tabs w-full grid xl:hidden gap-2">
                        {leftTabs.map((tab) => {
                            const isActive = activeLeftTab === tab.id;
                            return (
                                <div key={tab.id}>
                                    <div
                                        onClick={() => handleLeftTabClick(tab.id)}
                                        className={`cursor-pointer w-full px-3 py-2 rounded-lg flex items-center justify-start gap-3 transition-colors ${isActive ? "bg-purple-300 text-black" : "bg-transparent hover:bg-purple-200 hover:text-black"}`}>
                                        {tab.icon}
                                        <p>{tab.label}</p>
                                        {tab.id === "History" && (
                                            <ChevronDown className={`ml-auto h-4 w-4 transition-transform duration-200 ${isHistoryOpen ? "rotate-180" : ""}`} />
                                        )}
                                    </div>
                                    {tab.id === "History" && isHistoryOpen && (
                                        <div className="mt-3 ml-3 space-y-2 border-l border-purple-200 pl-3">
                                            {historyItems.map((item) => (
                                                <button
                                                    key={item}
                                                    type="button"
                                                    className="block w-full text-left text-xs text-gray-600 hover:text-purple-700"
                                                >
                                                    {item}
                                                </button>
                                            ))}
                                        </div>
                                    )}
                                </div>
                            );
                        })}
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
                            <p className="font-bold text-black pl-10">Welcome, John</p>
                        </div>

                        {/* input box parent */}
                        <div className="flex justify-between items-center flex-grow">
                            {/*  input box */}
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
                            <div onClick={() => {setIsAiChatOpen(!isAiOpen)}} id="ai-chat-support" className="md:w-[100px] w-fit p-4 mt-auto shadow-md rounded-full cursor-pointer grid items-center justify-center ">
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
                                    {/* chat panel */}
                                    {(isAiOpen && !isProcessingRequest) && <div className="w-full h-[80%] flex flex-col items-center">
                                        <h1 className="text-black"><span id="gradient-text" className="bg-gradient-to-r from-[#be9ee2] to-white bg-clip-text text-transparent font-bold">Hy Dear</span> This is an AI assited chat</h1>
                                        <img src={gradientBg } alt="Robot AI" className="w-[35%]" style={{ width : "35%"}} />
                                        <p className="text-black pt-3">How can i help?</p>
                                        {/* input */}
                                        <div className="w-[70%] h-[20%] justify-self-center relative">
                                             <input 
                                                type="text"
                                                value={prompt}
                                                onChange={(e) => setPrompt(e.target.value)}
                                                // 🌟 Captures the Enter key natively and fires the clean string text
                                                onKeyDown={(e) => {
                                                if (e.key === "Enter" && !isPending && prompt.trim()) {
                                                    handleSendRequest(prompt);
                                                    setPrompt(""); // Instantly clear the inline input field state
                                                }
                                                }}
                                                placeholder="Type your message..."
                                                className={`pl-4 rounded-xl border red-800 mt-4 w-full h-full ${isProcessingRequest ? "hidden" : ""}`} 
                                                style={{ borderColor: "black" }}
                                            />
                                            <div className="">
                                                    {isPending ? (

                                                        <div className="relative w-full">                                                            
                                                            <button 
                                                                type="button" // 🌟 Changed from "submit" to "button" to avoid form triggers
                                                                onClick={() => {
                                                                if (!isPending && prompt.trim()) {
                                                                    handleSendRequest(prompt);
                                                                    setPrompt(""); // Clear input state on mouse click
                                                                }
                                                                }}
                                                                id="send-icon" 
                                                                className="animate-spin absolute top-[50%] right-[5%] cursor-pointer flex items-center justify-center"
                                                                disabled={isPending || !prompt.trim()}
                                                            >
                                                                <SendHorizontal />            
                                                            </button>
                                                        </div>

                                                        
                                                    ) : (                                                            
                                                            <button 
                                                                type="button" // Changed from "submit" to "button"
                                                                onClick={() => {
                                                                if (prompt.trim()) {
                                                                    handleSendRequest(prompt);
                                                                    setPrompt(""); // Clear input state on mouse click
                                                                }
                                                                }}
                                                                id="send-icon" 
                                                                className="absolute top-[50%] right-[5%] cursor-pointer bg-transparent border-none p-0 flex items-center justify-center"
                                                            >
                                                                <SendHorizontal />            
                                                            </button>

                                                    )}
                                                
                                            </div>
                                        </div>
                                    </div>}

                                    {isAiOpen && (
                                        <div className="w-full h-[80%]">
                                        {/* The Chat box stays mounted on your dashboard screen layout permanently */}
                                        <AIChat 
                                            messages={messages}
                                            onSendMessage={(text) => handleSendRequest(text)}
                                            // The loader spinner itself handles turning on/off cleanly inside the file
                                            isAiLoading={isProcessing} 
                                        />
                                        </div>
                                    )}

                                        
                                </div>
                                
                            </div>
                        </div>)}
                    </div>

                    {/* right bar */}
                    <div className="w-[25%] h-full pt-3 items-start gap-4 pl-4 hidden lg:flex flex-col justify-start">

                        {/* Include your absolute rendering portal layer down at the bottom of the node string tree */}
                        <WorkspaceModal
                            isOpen={isModalOpen}
                            onClose={() => setIsModalOpen(false)}
                            allRepositories={items || []} 
                            selectedIds={selectedIdsSet}               
                            onToggleSelect={toggleSelect}               
                            onSubmit={handleCreateWorkspace}
                            isPending={useCreateRepos.isPending}
                        />
                        
                        <div className="w-full flex items-center gap-3">
                            {/* workspace List */}
                            <div className="">
                                <WorkspaceDropdown
                                    workspaces={data?.uniqueWorkspaces || ["olive corp"]}
                                    selectedWorkspace={selectedWorkspace}
                                    onSelectWorkspace={setSelectedWorkspace}
                                />
                            </div>
                            <button 
                                onClick={() => setIsModalOpen(true)}
                                className="p-1 bg-green-500 hover:bg-green-700 text-white rounded-full shadow-sm transition-colors cursor-pointer"
                                >
                                <Plus className="w-5 h-5" />
                            </button>
                        </div>
                        {/* create env variables */}
                        <div className="w-[161.61px] flex gap-2 px-4 py-2.5 bg-white border border-gray-300 rounded-xl cursor-pointer hover:bg-gray-50 transition-colors shadow-sm select-none"
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
                        <div className="w-[161.61px] px-4 py-2.5 bg-white border border-gray-300 rounded-xl cursor-pointer hover:bg-gray-50 transition-colors shadow-sm select-none"
                            onClick={() => setShowLlmModal(!showLlmModal)}
                        >
                            <span className="text-sm font-semibold text-gray-700">
                            Select LLM
                            </span>
                        </div> 
                        {showLlmModal &&<LLMConfigModal isOpen={showLlmModal} onClose={() => setShowLlmModal(false)}/> }

                    </div>  
        </div>
            </div>
        
        </div>

        <GitHubInstallation
            isOpen={showInstallModal}
            onClose={() => setShowInstallModal(false)}
        />
        </>
    );
    
}
