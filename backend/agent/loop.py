from backend.core.logger import logger
import json

class Planner:
    def __init__(self, model, tools_schema, emitter=None):
        self.model = model
        self.tools_schema = tools_schema
        self.emitter = emitter

    def plan(self, user_request: str, memory_context: str = "") -> list:
        logger.info("[Planner] Analyzing request and building task plan...")
        if self.emitter:
            self.emitter.emit("agent_step", {"stage": "planner", "message": "Analyzing intent & building Task Plan using Qwen..."})

        sys_msg = "You are Jarvis, an advanced desktop AI. If the user's request requires a desktop action or web search, select the correct tool. Do not converse or explain, just use the tool if needed."
        if memory_context:
            sys_msg += f"\n\n{memory_context}"

        messages = [
            {"role": "system", "content": sys_msg},
            {"role": "user", "content": user_request}
        ]

        tool_calls = []
        for chunk in self.model.generate(messages, tools=self.tools_schema):
            if chunk.get("done"):
                tool_calls = chunk.get("tool_calls", [])
                break

        tasks = []
        for tc in tool_calls:
            tasks.append({
                "action": tc.get("name"),
                "params": tc.get("arguments", {})
            })

        logger.debug(f"[Planner] Task Breakdown: {tasks}")
        return tasks


class Executor:
    def __init__(self, tools_registry, emitter=None):
        self.tools = tools_registry
        self.emitter = emitter

    def execute(self, tasks: list) -> list:
        logger.info(f"[Executor] Executing {len(tasks)} tasks sequentially...")
        results = []
        for task in tasks:
            logger.debug(f"  -> Running Tool: {task['action']} | Params: {task['params']}")
            
            if self.emitter:
                self.emitter.emit("tool_execution_start", {"tool": task['action'], "params": task['params']})
            
            result_data = self.tools.execute_tool(task['action'], task['params'])
            
            if self.emitter:
                self.emitter.emit("tool_execution_result", result_data)
                
            results.append(result_data)
            
        return results


class Verifier:
    def __init__(self, model, emitter=None):
        self.model = model
        self.emitter = emitter

    def verify(self, user_request: str, execution_results: list) -> dict:
        logger.info("[Verifier] Cross-referencing tool outputs against original intent...")
        if self.emitter:
            self.emitter.emit("agent_step", {"stage": "verifier", "message": "Validating tool outputs against request intent."})
        
        failures = [r for r in execution_results if r.get("status") != "success"]
        is_valid = len(failures) == 0
        return {"is_valid": is_valid, "retry_needed": not is_valid}


class AgentLoop:
    def __init__(self, model_service, memory_manager, tool_registry, emitter=None, voice_engine=None):
        logger.info("  [Module] AgentLoop initialized.")
        self.model = model_service
        self.memory = memory_manager
        self.tools = tool_registry
        self.emitter = emitter
        self.voice = voice_engine
        
        self.tools_schema = self.tools.get_schema()
        import threading
        self.lock = threading.Lock()
        
        # Instantiate internal pipeline stages
        self.planner = Planner(self.model, self.tools_schema, self.emitter)
        self.executor = Executor(self.tools, self.emitter)
        self.verifier = Verifier(self.model, self.emitter)

    def run_loop(self, user_request: str) -> str:
        if not self.lock.acquire(blocking=False):
            logger.warning("[Agent] Ignored stacked request. Agent is currently busy.")
            if self.emitter:
                self.emitter.emit("final_response", {"text": "I am currently processing another task. Please wait."})
            return "Busy"
            
        try:
            logger.info(f"\n=========================================")
            logger.info(f" [AGENT] Incoming Request: '{user_request}'")
            logger.info(f"=========================================")
            
            # 0. MEMORY RETRIEVAL
            logger.info("[Agent] Retrieving relevant context from Memory...")
            if self.emitter:
                self.emitter.emit("agent_step", {"stage": "memory", "message": "Retrieving context from Qdrant vector store..."})
                
            retrieved_memories = self.memory.retrieve_memory(user_request)
            memory_context = ""
            if retrieved_memories:
                mem_list = [f"- [{m['type'].upper()}] {m['content']}" for m in retrieved_memories[:3]]
                memory_context = "Relevant Context from Memory:\n" + "\n".join(mem_list)
                logger.debug(f"[Agent] Injected context:\n{memory_context}")
            
            # 1. PLANNER
            tasks = self.planner.plan(user_request, memory_context)
            
            # If no tasks are needed, converse normally
            if not tasks:
                logger.info("[Agent] No tools required. Synthesizing standard response...")
                sys_msg = "You are Jarvis, a concise desktop AI system. Answer the user briefly."
                if memory_context:
                    sys_msg += f"\n\n{memory_context}"
                    
                messages = [
                    {"role": "system", "content": sys_msg},
                    {"role": "user", "content": user_request}
                ]
                final_answer = ""
                current_sentence = ""
                for chunk in self.model.generate(messages):
                    if not chunk.get("done"):
                        text_chunk = chunk.get("content", "")
                        final_answer += text_chunk
                        current_sentence += text_chunk
                        
                        if any(punct in text_chunk for punct in ['. ', '? ', '! ', '\n']):
                            sentence = current_sentence.strip()
                            if sentence and self.voice:
                                self.voice.speak(sentence)
                            current_sentence = ""
                
                # Speak remaining
                sentence = current_sentence.strip()
                if sentence and self.voice:
                    self.voice.speak(sentence)
                    
                if self.emitter:
                    self.emitter.emit("final_response", {"text": final_answer})
                    
                return final_answer
                
            # 2. EXECUTOR
            results = self.executor.execute(tasks)
            
            # 3. VERIFIER
            validation = self.verifier.verify(user_request, results)
            if validation["retry_needed"]:
                logger.warning("[Agent] Verification failed.")
                err_msg = "I encountered an error executing the requested tools."
                if self.emitter:
                    self.emitter.emit("final_response", {"text": err_msg})
                if self.voice:
                    import threading
                    threading.Thread(target=self.voice.speak, args=(err_msg,), daemon=True).start()
                return "Execution failed."
                
            # 4. FINAL RESPONSE
            logger.info("[Agent] Synthesizing final user response...")
            if self.emitter:
                self.emitter.emit("agent_step", {"stage": "synthesis", "message": "Synthesizing final response..."})
                
            sys_msg = "You are Jarvis. You executed tools to fulfill a user request. Summarize the outcome based on the execution results below concisely."
            exec_context = json.dumps(results)
            messages = [
                {"role": "system", "content": f"{sys_msg}\nExecution Results: {exec_context}"},
                {"role": "user", "content": user_request}
            ]
            
            final_answer = ""
            current_sentence = ""
            for chunk in self.model.generate(messages):
                if not chunk.get("done"):
                    text_chunk = chunk.get("content", "")
                    final_answer += text_chunk
                    current_sentence += text_chunk
                    
                    if any(punct in text_chunk for punct in ['. ', '? ', '! ', '\n']):
                        sentence = current_sentence.strip()
                        if sentence and self.voice:
                            self.voice.speak(sentence)
                        current_sentence = ""
            
            # Speak remaining
            sentence = current_sentence.strip()
            if sentence and self.voice:
                self.voice.speak(sentence)
                
            logger.info(f"[Agent] Pipeline Complete. Output: '{final_answer}'\n")
            
            if self.emitter:
                self.emitter.emit("final_response", {"text": final_answer})
                
            # 5. MEMORY STORAGE
            if tasks and validation["is_valid"]:
                store_msg = f"User requested: '{user_request}'. Actions taken: {len(tasks)} tools executed. Outcome: {final_answer}"
                self.memory.add_memory("short_term", store_msg)
                logger.info("[Agent] Stored successful execution outcome in short_term memory.")
                if self.emitter:
                    self.emitter.emit("agent_step", {"stage": "memory", "message": "Stored execution outcome in short-term memory."})
                
            return final_answer
            
        except Exception as e:
            logger.error(f"[AgentLoop] Critical failure in loop: {e}")
            err_msg = f"I encountered an internal error: {e}"
            if self.emitter:
                self.emitter.emit("final_response", {"text": err_msg})
            if self.voice:
                self.voice.speak("I encountered an internal error.")
            return "Error"

        finally:
            self.lock.release()
