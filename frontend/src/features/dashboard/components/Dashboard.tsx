import { Bot, CheckCheck, Menu, Search, SendHorizontal, ChevronLeft } from "lucide-react";
import { useSelectionStore } from "../../store/selectionStore";
import { useRepos } from "@/features/github/hooks/useRepos";
import { items as dummyItems } from "@/features/data/dummyData";
import { useStreamingSocket } from "@/features/streaming/hooks/useStreamingSocket";
import LiveTerminal from "@/features/streaming/components/LiveTerminal";
import { useState } from "react";
import gradientBg  from "../../../assets/gradient.jpg"
import { RepoCard } from "./RepoCard";
import { SelectionToolbar } from "./SelectionToolbar";


export default function Dashboard() {
    const [isAiOpen, setIsAiOpen] = useState(false);
    const [isProcessingRequest, setIsProcessingRequest] = useState(false);
    const [isOn, setIsOn] = useState(false);
    const [switchBetweenAIPage, setSwitchBetweenAIPage] = useState(false);
    const [prompt, setPrompt] = useState("");
    const { sendMessage } = useStreamingSocket();
    const selected = useSelectionStore((state) => state.selected);
    
    const {
        data,
        isLoading,
        error,
    } = useRepos();


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
                            <input id="input-search" type="text" placeholder="Search projects, Tasks, etc..."
                                className="pl-4 rounded-xl h-[25px] w-full shadow-lg" />
                            <div id="search-icon">
                                <Search className="w-4 h-4 text-gray-500" />
                            </div>

                            {/* <i class="material-icons-outlined cursor-pointer absolute text-black right-2 top-1">search_outlined</i> */}
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
                <div className="h-full w-[72%] flex-grow mt-4 pr-4 pl-2">               
                    {/* repo menu */}                 

                    {(!isAiOpen && !isProcessingRequest) && (<div className="p-10">
                        <SelectionToolbar switchOn = {setIsOn} isOn = {isOn} />

                        <div className="space-y-4">
                            {dummyItems.map((repo) => (
                            <RepoCard
                                key={repo.id}
                                id={repo.id}
                                name={repo.full_name}
                            />
                            ))}
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
                            <p>Request status: {switchBetweenAIPage ? "aipageon..." : "Idle"}</p>
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
                <div className="w-[25%] h-full pl-4 hidden lg:block">
                    right bar placeholder
                </div>  
    </div>
        </div>
            </div>
        </div>);
        
}